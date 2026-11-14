from django.contrib import admin

from .models import Chapter, Question, Subtopic

admin.site.register(Chapter)
admin.site.register(Subtopic)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "subtopic", "difficulty", "correct_option", "active")
    list_filter = ("active", "difficulty", "subtopic__chapter__subject")
    list_editable = ("difficulty", "correct_option", "active")
    readonly_fields = ("fingerprint", "artwork", "hint")
    search_fields = ("subtopic__name", "subtopic__chapter__name")

    def has_add_permission(self, request):
        return False
