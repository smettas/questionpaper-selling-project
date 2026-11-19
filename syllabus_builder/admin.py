from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import CorrectionReport

@admin.register(CorrectionReport)
class CorrectionReportAdmin(admin.ModelAdmin):
    list_display = ("id", "question_id", "category", "status", "created_at")
    list_filter = ("status", "category", "question__subtopic__chapter__subject")
    search_fields = ("note", "question__subtopic__name", "question__subtopic__chapter__name")
    readonly_fields = ("question", "question_editor", "category", "note", "snapshot", "reporter", "created_at", "updated_at")
    exclude = ("session_key",)
    list_select_related = ("question",)

    @admin.display(description="Review original question")
    def question_editor(self, obj):
        return format_html('<a href="{}">Open question {} for correction</a>',
                           reverse("admin:question_bank_question_change", args=[obj.question_id]), obj.question_id)

    def has_add_permission(self, request):
        return False
