from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("question_bank", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="question",
            name="hint",
            field=models.ImageField(blank=True, upload_to="hints/"),
        ),
    ]
