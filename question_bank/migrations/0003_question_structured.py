from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("question_bank", "0002_question_hint")]

    operations = [
        migrations.AddField(
            model_name="question",
            name="structured",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
