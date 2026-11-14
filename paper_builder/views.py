import json
import random
import zipfile
from io import BytesIO

from django import forms
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from PIL import Image

from question_bank.models import Chapter, Question, Subtopic

from .pdf import build_pdf


class PaperDetails(forms.Form):
    institution = forms.CharField(max_length=120, required=False)
    title = forms.CharField(max_length=120, required=False)
    date = forms.DateField(input_formats=["%Y-%m-%d"], required=False)
    start_number = forms.IntegerField(min_value=1, max_value=9999, required=False)
    end_number = forms.IntegerField(min_value=1, max_value=9999, required=False)
    marks = forms.IntegerField(min_value=1, max_value=10000, required=False)
    duration = forms.IntegerField(min_value=1, max_value=1440, required=False)


def allocate_sections(requests, eligible):
    # Match each requested slot to a distinct question. If two sections
    # overlap, reassign an earlier slot before declaring a shortage.
    pools = []
    owners = {}
    for subject, count, candidates in requests:
        if len(candidates) < count:
            raise ValueError(f"{subject} has only {len(candidates)} matching questions.")
        pool = sorted(candidates)
        random.shuffle(pool)
        pools.append(pool)

    def assign(section, visited):
        for question_id in pools[section]:
            if question_id in visited:
                continue
            visited.add(question_id)
            previous = owners.get(question_id)
            if previous is None or assign(previous, visited):
                owners[question_id] = section
                return True
        return False

    for index, (subject, count, _) in enumerate(requests):
        for _ in range(count):
            if not assign(index, set()):
                raise ValueError(f"Section {index + 1} overlaps another selection. Reduce the counts or change the filters.")

    questions = eligible.in_bulk(owners.keys())
    if len(questions) != len(owners):
        raise ValueError("The question bank changed. Refresh and try again.")
    selected = [(subject, []) for subject, _, _ in requests]
    for question_id, index in owners.items():
        selected[index][1].append(questions[question_id])
    return selected


@require_GET
def builder(request):
    chapters = list(Chapter.objects.values("id", "subject", "level", "name"))
    topics = list(Subtopic.objects.values("id", "chapter_id", "name"))
    counts = list(Question.objects.filter(active=True).values("subtopic_id", "difficulty").annotate(total=Count("id")))
    return render(request, "paper_builder/index.html", {
        "catalog": {"chapters": chapters, "topics": topics, "counts": counts},
    })


@require_POST
def download(request):
    form = PaperDetails(request.POST)
    if not form.is_valid():
        return HttpResponse(" ".join(f"{field.replace('_', ' ').capitalize()}: {' '.join(errors)}"
                                     for field, errors in form.errors.items()),
                            status=400, content_type="text/plain")
    details = {**form.cleaned_data, "logo": None}
    details["start_number"] = details["start_number"] or 1
    try:
        sections = json.loads(request.POST.get("sections", "[]"))
        if not isinstance(sections, list) or not 1 <= len(sections) <= 12:
            raise ValueError("Add 1 to 12 sections.")
        logo = request.FILES.get("logo")
        if logo:
            if logo.size > 2_000_000:
                raise ValueError("Logo must be under 2 MB.")
            try:
                with Image.open(logo) as image:
                    if image.format not in ("PNG", "JPEG", "WEBP") or max(image.size) > 4096:
                        raise ValueError("Use a PNG, JPEG or WebP logo up to 4096 pixels per side.")
                    image.thumbnail((600, 300))
                    buffer = BytesIO()
                    image.convert("RGBA").save(buffer, "PNG")
                    details["logo"] = buffer.getvalue()
            except (OSError, Image.DecompressionBombError) as exc:
                raise ValueError("The logo could not be opened.") from exc

        eligible = Question.objects.filter(active=True)
        subjects = dict(Chapter.Subject.choices)
        requests = []
        for section in sections:
            if not isinstance(section, dict):
                raise ValueError("Invalid section.")
            subject, difficulty = section.get("subject"), section.get("difficulty")
            count = int(section.get("count"))
            if subject not in subjects or difficulty not in ["", *Question.Difficulty.values] or count < 1:
                raise ValueError("Check the subject, difficulty and quantity for each section.")
            query = eligible.filter(subtopic__chapter__subject=subject)
            if section.get("chapter"):
                query = query.filter(subtopic__chapter_id=int(section["chapter"]))
            if section.get("topic"):
                query = query.filter(subtopic_id=int(section["topic"]))
            if difficulty:
                query = query.filter(difficulty=difficulty)
            candidates = set(query.values_list("pk", flat=True))
            requests.append((subjects[subject], count, candidates))
        total = sum(count for _, count, _ in requests)
        if total > 300:
            raise ValueError("Use up to 300 questions per paper.")
        last_number = details["start_number"] + total - 1
        if last_number > 9999:
            raise ValueError("The last question number must be 9999 or lower.")
        if details["end_number"] is not None and details["end_number"] != last_number:
            raise ValueError(f"{total} questions starting at {details['start_number']} must end at {last_number}.")
        selected = allocate_sections(requests, eligible)
    except (ValueError, TypeError) as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain")

    bundle = BytesIO()
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Question Paper.pdf", build_pdf(details, selected))
        archive.writestr("Answer Key.pdf", build_pdf(details, selected, answer_key=True))
    response = HttpResponse(bundle.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="NEET Paper and Answer Key.zip"'
    return response
