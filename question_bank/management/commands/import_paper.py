from hashlib import sha256
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from question_bank.models import Chapter, Question, Subtopic
from question_bank.pdf_import import (
    MAX_BYTES, NUMBER, inspect_papers, missing_option_markers, pdfium, pdfplumber, render_crop,
)


def reuse_named_entry(model, name, **scope):
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > 150:
        raise CommandError("Chapter and subtopic names must contain 1 to 150 characters.")
    entries = model.objects.filter(**scope).order_by("pk")
    exact = entries.filter(name=cleaned).first()
    if exact:
        return exact
    normalized = cleaned.casefold()
    for entry in entries:
        if " ".join(entry.name.split()).casefold() == normalized:
            return entry
    return model.objects.get_or_create(name=cleaned, **scope)[0]


class Command(BaseCommand):
    help = "Import a numbered question PDF and matching answer PDF into one NEET subtopic."

    def add_arguments(self, parser):
        parser.add_argument("questions", type=Path)
        parser.add_argument("answers", type=Path)
        parser.add_argument("--count", type=int, required=True)
        parser.add_argument("--subject", choices=Chapter.Subject.values, required=True)
        parser.add_argument("--level", type=int, choices=(11, 12), required=True)
        parser.add_argument("--chapter", required=True)
        parser.add_argument("--subtopic", required=True)
        parser.add_argument("--difficulty", choices=Question.Difficulty.values, required=True)
        parser.add_argument("--publish", action="store_true")

    def handle(self, *args, **options):
        count = options["count"]
        if not 1 <= count <= 300:
            raise CommandError("Count must be between 1 and 300.")
        try:
            sources = [options[key] for key in ("questions", "answers")]
            if any(path.stat().st_size > MAX_BYTES for path in sources):
                raise ValueError("Each PDF must be 25 MB or smaller.")
            questions, answers = (path.read_bytes() for path in sources)
            specs = inspect_papers(questions, answers, count)
            prepared = []
            warnings = []
            with pdfplumber.open(sources[0]) as text, pdfium.PdfDocument(questions) as document:
                words = [page.extract_words() for page in text.pages]
                for number, boxes, answer, _ in specs:
                    page, left, top, right, bottom = boxes[0]
                    candidates = [word for word in words[page - 1]
                                  if left <= word["x0"] <= left + 50
                                  and top <= word["top"] < min(bottom, top + 35)]
                    label = next((word for word in candidates
                                  if NUMBER.fullmatch(word["text"]) and int(word["text"][:-1]) == number), None)
                    if label is None:
                        label = next((word for word in candidates if word["text"] == str(number)), None)
                        if label is not None:
                            dot = next((word for word in candidates if word["text"] in (".", ")")
                                        and 0 <= word["x0"] - label["x1"] <= label["height"]
                                        and abs(word["bottom"] - label["bottom"]) < 2), None)
                            label = {**label, "x1": dot["x1"]} if dot else None
                    if label is None:
                        raise ValueError(f"Could not isolate the printed number for question {number}.")
                    mask = tuple(label[key] for key in ("x0", "top", "x1", "bottom"))
                    missing = missing_option_markers(document, boxes)
                    if missing:
                        warnings.append(number)
                    image, _, _ = render_crop(document, boxes, first_mask=mask)
                    prepared.append((answer, image, sha256(image).hexdigest(), bool(missing)))
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        saved = []
        try:
            with transaction.atomic():
                chapter = reuse_named_entry(
                    Chapter, options["chapter"], subject=options["subject"], level=options["level"],
                )
                subtopic = reuse_named_entry(Subtopic, options["subtopic"], chapter=chapter)
                for answer, image, fingerprint, needs_review in prepared:
                    existing = Question.objects.filter(fingerprint=fingerprint).first()
                    if existing:
                        if existing.correct_option != answer:
                            raise CommandError(f"Conflicting answer key for existing question {existing.pk}.")
                        continue
                    question = Question(
                        subtopic=subtopic, difficulty=options["difficulty"], correct_option=answer,
                        fingerprint=fingerprint, active=options["publish"] and not needs_review,
                    )
                    question.artwork.save(f"{fingerprint}.webp", ContentFile(image), save=False)
                    saved.append(question.artwork)
                    question.save()
        except Exception:
            for asset in saved:
                asset.storage.delete(asset.name)
            raise
        self.stdout.write(self.style.SUCCESS(f"Imported {len(saved)} new questions. Skipped {count - len(saved)} duplicates."))
        if warnings:
            self.stdout.write(self.style.WARNING(f"Check option labels before activating source questions: {warnings}."))
