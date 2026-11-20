import json
from uuid import UUID
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from syllabus_builder.views import json_body, ids, serialize
from .core import available_catalog, missing_chapters, validate_spec, choose_section, metadata, SECTIONS
from .models import TestPlan


def error(exc):
    return JsonResponse({"error": str(exc)}, status=400)


@never_cache
@require_GET
def catalog(request):
    chapters, topics = available_catalog()
    return JsonResponse({"chapters": chapters, "topics": topics, "missing": missing_chapters(chapters)})


@never_cache
@require_POST
def generate(request):
    try:
        data = json_body(request)
        spec = validate_spec(data)
        rows = []
        for section in SECTIONS:
            if section in spec["targets"]:
                rows.extend(metadata(choose_section(spec, section), section))
        plan = TestPlan.objects.create(profile=spec["profile"], specification=spec)
        return JsonResponse({"plan_id": str(plan.pk), "questions": rows, "total": spec["total"],
                             "marks": spec["marks"], "targets": spec["targets"]})
    except ValueError as exc:
        return error(exc)


@never_cache
@require_POST
def replace(request):
    try:
        data = json_body(request)
        try:
            plan_id = UUID(str(data.get("plan_id", "")))
        except ValueError as exc:
            raise ValueError("This test plan is unavailable. Generate the test again.") from exc
        plan = get_object_or_404(TestPlan, pk=plan_id)
        section = data.get("section")
        if section not in plan.specification["targets"]:
            raise ValueError("Invalid test section.")
        excluded = ids(data.get("exclude", []), "excluded question", 10000)
        rows = choose_section(plan.specification, section, excluded, count=1)
        item = metadata(rows, section)[0]
        from question_bank.models import Question
        row = Question.objects.select_related("subtopic__chapter").get(pk=item["id"], active=True)
        return JsonResponse({"question": {**item, **serialize(row)}})
    except ValueError as exc:
        return error(exc)
