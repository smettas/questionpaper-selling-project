from django.db.models.signals import pre_save
from django.dispatch import receiver
from question_bank.models import Question
from question_bank.question_types import classify_question

@receiver(pre_save, sender=Question, dispatch_uid="ojas_syllabus_classify")
def classify_saved_question(sender, instance, update_fields=None, **kwargs):
    # Normal imports already set these. Also keep manual admin edits in sync.
    if update_fields is not None and "structured" not in update_fields:
        return
    if instance.structured:
        kind, visual = classify_question(instance.structured, instance.structured.get("type", ""))
        instance.question_kind, instance.question_visual = kind, visual

from django.db.models.signals import post_save

@receiver(post_save, sender=Question, dispatch_uid="ojas_syllabus_classify_partial")
def persist_partial_classification(sender, instance, update_fields=None, **kwargs):
    if update_fields is not None and "structured" in update_fields and instance.structured:
        missing = {"question_kind", "question_visual"} - set(update_fields)
        if missing:
            sender.objects.filter(pk=instance.pk).update(**{key: getattr(instance, key) for key in missing})
