from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion
class Migration(migrations.Migration):
    dependencies=[('faculty_studio','0003_recharge_one_approved_payment_reference'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name='policy',name='practice_correct_per_credit',field=models.PositiveSmallIntegerField(default=5)),
        migrations.AddField(model_name='policy',name='welcome_credits',field=models.PositiveIntegerField(default=50)),
        migrations.AddField(model_name='profile',name='practice_progress',field=models.PositiveSmallIntegerField(default=0)),
        migrations.CreateModel(name='WelcomeClaim',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('email',models.CharField(blank=True,max_length=254,null=True,unique=True)),('created_at',models.DateTimeField(auto_now_add=True)),('user',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL))]),
    ]
