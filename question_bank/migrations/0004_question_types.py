from django.db import migrations, models

from question_bank.question_types import classify_question


def fill_question_types(apps, schema_editor):
    question = apps.get_model("question_bank", "Question")
    rows = question.objects.using(schema_editor.connection.alias)
    last_pk = 0
    while True:
        batch = list(rows.filter(pk__gt=last_pk).exclude(structured={})
                     .order_by("pk").only("structured")[:100])
        if not batch:
            break
        last_pk = batch[-1].pk
        changed = []
        for row in batch:
            kind, visual = classify_question(row.structured, row.structured.get("type"))
            if kind != "mcq" or visual:
                row.question_kind, row.question_visual = kind, visual
                changed.append(row)
        rows.bulk_update(changed, ["question_kind", "question_visual"])


class Migration(migrations.Migration):
    dependencies = [("question_bank", "0003_question_structured")]

    operations = [
        migrations.AddField(
            model_name="question", name="question_kind",
            field=models.CharField(max_length=16, default="mcq", db_index=True),
        ),
        migrations.AddField(
            model_name="question", name="question_visual",
            field=models.CharField(max_length=8, blank=True, default="", db_index=True),
        ),
        migrations.RunPython(fill_question_types, migrations.RunPython.noop),
    ]
