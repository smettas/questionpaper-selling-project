import json
from base64 import b64encode
from io import BytesIO

from django import forms
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from PIL import Image

from question_bank.models import Chapter, Question, Subtopic

from .pdf import build_pdf
from .word import build_word


class PaperDetails(forms.Form):
    option_layout = forms.ChoiceField(choices=[(v, v) for v in ("one", "two", "four")], required=False)
    page_columns = forms.ChoiceField(choices=[(v, v) for v in ("one", "two")], required=False)
    arrangement = forms.ChoiceField(choices=[(v, v) for v in ("separate", "combined", "paired")], required=False)
    output_format = forms.ChoiceField(choices=[(v, v) for v in ("pdf", "docx", "both")], required=False)
    institution = forms.CharField(max_length=120, required=False)
    title = forms.CharField(max_length=120, required=False)
    date = forms.DateField(input_formats=["%Y-%m-%d"], required=False)
    start_number = forms.IntegerField(min_value=1, max_value=9999, required=False)
    end_number = forms.IntegerField(min_value=1, max_value=9999, required=False)
    marks = forms.IntegerField(min_value=1, max_value=10000, required=False)
    duration = forms.IntegerField(min_value=1, max_value=1440, required=False)


@require_GET
def builder(request):
    chapters = list(Chapter.objects.values("id", "subject", "level", "name"))
    topics = list(Subtopic.objects.values("id", "chapter_id", "name"))
    return render(request, "paper_builder/index.html", {
        "catalog": {"chapters": chapters, "topics": topics},
    })


@require_GET
def browse_questions(request):
    subjects = dict(Chapter.Subject.choices)
    subject = request.GET.get("subject", "")
    difficulty = request.GET.get("difficulty", "")
    if subject not in subjects or difficulty not in ("", *Question.Difficulty.values):
        return JsonResponse({"error": "Choose a subject and difficulty."}, status=400)
    query = Question.objects.filter(active=True, subtopic__chapter__subject=subject)
    if difficulty:
        query = query.filter(difficulty=difficulty)
    for key, field in (("chapter", "subtopic__chapter_id"), ("topic", "subtopic_id")):
        value = request.GET.get(key)
        if value:
            if not value.isascii() or not value.isdecimal() or len(value) > 18:
                return JsonResponse({"error": "Invalid filter."}, status=400)
            query = query.filter(**{field: int(value)})
    paginator = Paginator(query.order_by("pk"), 12)
    page = paginator.get_page(request.GET.get("page", 1))
    return JsonResponse({
        "count": paginator.count, "page": page.number, "pages": paginator.num_pages,
        "questions": [{
            "id": row.pk, "subject": subjects[subject], "answer": row.correct_option,
            "structured": bool(row.structured),
            "image": reverse("question-asset", args=[row.pk, "question"]),
            "hint": reverse("question-asset", args=[row.pk, "hint"]) if row.hint or row.structured else None,
        } for row in page],
    })


@require_GET
def question_asset(request, pk, kind):
    question = get_object_or_404(Question, pk=pk, active=True)
    if question.structured and kind in ("question", "hint"):
        details = dict(title="", institution="", logo=None, date=None, marks=None, duration=None, start_number=1)
        return HttpResponse(build_pdf(details, [("Preview", [question])], answer_key=kind == "hint", preview=True),
                            content_type="application/pdf")
    asset = {"question": question.artwork, "hint": question.hint}.get(kind)
    if not asset:
        raise Http404
    return FileResponse(asset.open("rb"), content_type="image/webp")


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
        ids = json.loads(request.POST.get("question_ids", "[]"))
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 300
                or any(type(pk) is not int or not 1 <= pk < 2**63 for pk in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError("Pick between 1 and 300 distinct questions.")
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

        rows = Question.objects.filter(active=True).select_related("subtopic__chapter").in_bulk(ids)
        if len(rows) != len(ids):
            raise ValueError("A selected question is no longer available. Refresh and pick again.")
        total = len(ids)
        last_number = details["start_number"] + total - 1
        if last_number > 9999:
            raise ValueError("The last question number must be 9999 or lower.")
        if details["end_number"] is not None and details["end_number"] != last_number:
            raise ValueError(f"{total} questions starting at {details['start_number']} must end at {last_number}.")
        selected = []
        for pk in ids:
            question = rows[pk]
            subject = question.subtopic.chapter.get_subject_display()
            if not selected or selected[-1][0] != subject:
                selected.append((subject, []))
            selected[-1][1].append(question)
    except (ValueError, TypeError) as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain")

    arrangement = details["arrangement"] or "separate"
    output_format = details["output_format"] or "pdf"
    modes = [("question", "Question Paper"), ("answer", "Answer Key")] if arrangement == "separate" else [
        (arrangement, "Question Paper and Answers" if arrangement == "combined" else "Questions with Answers")]
    files = []
    try:
        for mode, title in modes:
            if output_format in ("pdf", "both"):
                files.append({"name": f"{title}.pdf", "type": "application/pdf",
                              "data": b64encode(build_pdf(details, selected, mode=mode)).decode("ascii")})
            if output_format in ("docx", "both"):
                files.append({"name": f"{title}.docx",
                              "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                              "data": b64encode(build_word(details, selected, mode)).decode("ascii")})
    except ValueError as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain")
    response = JsonResponse({"files": files})
    response["Cache-Control"] = "no-store"
    return response
