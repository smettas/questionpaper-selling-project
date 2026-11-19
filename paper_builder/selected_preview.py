"""Read-only preview for a selected, published question."""
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from question_bank.models import Question


@never_cache
@require_GET
def selected_question(request, pk):
    # Reuse the installed renderer, including its latest equation fixes.
    from .views import inline_preview

    row = get_object_or_404(
        Question.objects.select_related("subtopic__chapter"), pk=pk, active=True,
    )
    chapter = row.subtopic.chapter
    return JsonResponse({
        "id": row.pk,
        "subject": chapter.get_subject_display(),
        "chapter": chapter.name,
        "level": chapter.level,
        "subtopic": row.subtopic.name,
        "difficulty": row.get_difficulty_display(),
        "answer": row.correct_option,
        "preview": inline_preview(row.structured),
        "image": reverse("question-asset", args=[row.pk, "question"]),
        "hint": reverse("question-asset", args=[row.pk, "hint"]) if row.hint or row.structured else None,
    })
