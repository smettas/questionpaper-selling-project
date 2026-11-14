from collections import Counter
from hashlib import sha256
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from paper_builder.structured import validate_content
from question_bank.chapter_zip import read_chapter_zip
from question_bank.models import Chapter, Question, Subtopic
from .import_paper import reuse_named_entry


class Command(BaseCommand):
    help = "Validate or import all parts in a structured chapter ZIP."

    def add_arguments(self, parser):
        parser.add_argument("archive", type=Path)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--publish", action="store_true")

    def handle(self, *args, **options):
        try:
            manifest, records = read_chapter_zip(options["archive"])
            for uid, _, _, _, content in records:
                try:
                    validate_content(content)
                except ValueError as exc:
                    raise ValueError(f"{uid}: {exc}") from exc
        except (ValueError, TypeError, KeyError, OSError, BadZipFile, ParseError, RuntimeError) as exc:
            raise CommandError(str(exc)) from exc
        counts = Counter((topic, difficulty) for _, topic, difficulty, _, _ in records)
        self.stdout.write(f"{manifest['chapter']}: {len(records)} validated questions"
                          f" ({'complete' if manifest['complete'] else 'partial'} package)")
        for (topic, difficulty), count in sorted(counts.items()):
            self.stdout.write(f"{topic} / {difficulty}: {count}")
        if options["dry_run"]:
            return

        created = updated = unchanged = 0
        with transaction.atomic():
            chapter = reuse_named_entry(Chapter, manifest["chapter"],
                                        subject=manifest["subject"], level=manifest["level"])
            topics = {topic: reuse_named_entry(Subtopic, topic, chapter=chapter) for topic, _ in counts}
            for uid, topic, difficulty, answer, content in records:
                fingerprint = sha256(f"structured-v1:{manifest['subject']}:{manifest['level']}:{uid}".encode()).hexdigest()
                values = dict(subtopic=topics[topic], difficulty=difficulty,
                              correct_option=answer, structured=content)
                question, new = Question.objects.get_or_create(
                    fingerprint=fingerprint, defaults={**values, "active": options["publish"]},
                )
                if new:
                    created += 1
                    continue
                if question.subtopic.chapter_id != chapter.pk:
                    raise CommandError(f"Question ID {uid} belongs to another chapter.")
                if options["publish"]:
                    values["active"] = True
                changed = [field for field, value in values.items() if getattr(question, field) != value]
                if changed:
                    for field in changed:
                        setattr(question, field, values[field])
                    question.save(update_fields=changed)
                    updated += 1
                else:
                    unchanged += 1
        self.stdout.write(self.style.SUCCESS(f"Created {created}; updated {updated}; unchanged {unchanged}."))
