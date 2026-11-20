import uuid
from django.db import migrations, models
class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(name="TestPlan", fields=[
        ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
        ("profile", models.CharField(max_length=16)),
        ("specification", models.JSONField(default=dict)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
    ], options={"ordering": ["-created_at"]})]
