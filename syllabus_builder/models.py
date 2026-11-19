from django.conf import settings
from django.db import models

class CorrectionReport(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWING = "reviewing", "Under review"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    question = models.ForeignKey("question_bank.Question", on_delete=models.PROTECT)
    category = models.CharField(max_length=24, choices=[
        ("question", "Question wording"), ("answer", "Answer key"),
        ("solution", "Explanation"), ("diagram", "Diagram / graph"),
        ("format", "Formatting"), ("other", "Other"),
    ])
    note = models.TextField(max_length=2000)
    snapshot = models.JSONField(default=dict)
    session_key = models.CharField(max_length=40, db_index=True)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True)
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report {self.pk}: Question {self.question_id}"
