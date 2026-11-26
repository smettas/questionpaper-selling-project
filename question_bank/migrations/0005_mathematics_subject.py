from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('question_bank', '0004_question_types')]
    operations = [migrations.AlterField(model_name='chapter', name='subject', field=models.CharField(max_length=16, choices=[('physics','Physics'),('chemistry','Chemistry'),('biology','Biology'),('mathematics','Mathematics')]))]
