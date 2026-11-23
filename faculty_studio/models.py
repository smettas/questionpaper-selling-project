from django.conf import settings
from django.db import models
from django.utils import timezone

class Policy(models.Model):
    # Singleton; all money is integer paise and all credits are integer units.
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    credits_per_question = models.PositiveSmallIntegerField(default=1)
    paise_per_credit = models.PositiveSmallIntegerField(default=10)
    practice_correct_per_credit = models.PositiveSmallIntegerField(default=5)
    welcome_credits = models.PositiveIntegerField(default=50)
    practice_per_correct = models.PositiveSmallIntegerField(default=1)
    practice_daily_cap = models.PositiveSmallIntegerField(default=20)
    credit_valid_days = models.PositiveSmallIntegerField(default=365)
    staff_free = models.BooleanField(default=True)
    registration_open = models.BooleanField(default=True)
    low_balance = models.PositiveIntegerField(default=100)
    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]
    def save(self,*a,**kw):
        self.pk=1
        super().save(*a,**kw)
    def __str__(self): return 'Credit and practice policy'

class Institution(models.Model):
    name=models.CharField(max_length=150)
    def __str__(self):return self.name

class Profile(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    practice_progress=models.PositiveSmallIntegerField(default=0)
    academy=models.CharField(max_length=150,blank=True)
    institution=models.ForeignKey(Institution,null=True,blank=True,on_delete=models.SET_NULL)
    def __str__(self):return self.user.get_username()

class Wallet(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.PROTECT)
    institution=models.OneToOneField(Institution,null=True,blank=True,on_delete=models.PROTECT)
    class Meta:
        constraints=[models.CheckConstraint(condition=(models.Q(user__isnull=False,institution__isnull=True)|models.Q(user__isnull=True,institution__isnull=False)),name='wallet_one_owner')]
    def __str__(self):return str(self.user or self.institution)

class Grant(models.Model):
    wallet=models.ForeignKey(Wallet,on_delete=models.PROTECT)
    amount=models.PositiveIntegerField()
    remaining=models.PositiveIntegerField()
    reason=models.CharField(max_length=150)
    reference=models.CharField(max_length=160,unique=True)
    created_at=models.DateTimeField(auto_now_add=True)
    expires_at=models.DateTimeField()
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(remaining__lte=models.F('amount')),name='grant_remaining_bound')]

class Ledger(models.Model):
    wallet=models.ForeignKey(Wallet,on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    amount=models.IntegerField()
    reason=models.CharField(max_length=150)
    reference=models.CharField(max_length=160,unique=True)
    created_at=models.DateTimeField(auto_now_add=True)

class Recharge(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    wallet=models.ForeignKey(Wallet,on_delete=models.PROTECT)
    rupees=models.PositiveIntegerField()
    credits=models.PositiveIntegerField()
    reference=models.CharField(max_length=100)
    status=models.CharField(max_length=12,default='pending',choices=[('pending','Pending'),('approved','Approved'),('rejected','Rejected')])
    created_at=models.DateTimeField(auto_now_add=True)
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    reviewed_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['user','reference'],name='recharge_user_reference'),models.UniqueConstraint(fields=['reference'],condition=models.Q(status='approved'),name='one_approved_payment_reference')]

class Pattern(models.Model):
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    name=models.CharField(max_length=120)
    spec=models.JSONField()
    updated_at=models.DateTimeField(auto_now=True)

class Draft(models.Model):
    import uuid
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    name=models.CharField(max_length=120)
    spec=models.JSONField()
    question_ids=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)

class Paper(models.Model):
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    wallet=models.ForeignKey(Wallet,on_delete=models.PROTECT)
    fingerprint=models.CharField(max_length=64)
    title=models.CharField(max_length=150)
    count=models.PositiveSmallIntegerField()
    charged=models.PositiveIntegerField()
    files=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['owner','fingerprint'],name='paper_owner_fingerprint')]

class Practice(models.Model):
    import uuid
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    question_ids=models.JSONField()
    answer_key=models.JSONField()
    submitted=models.BooleanField(default=False)
    answers=models.JSONField(default=dict)
    score=models.PositiveSmallIntegerField(default=0)
    reward=models.PositiveIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    submitted_at=models.DateTimeField(null=True,blank=True)

class RewardedQuestion(models.Model):
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    question=models.ForeignKey('question_bank.Question',on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['owner','question'],name='reward_once_per_question')]

class Promotion(models.Model):
    wallet=models.ForeignKey(Wallet,on_delete=models.PROTECT)
    credits=models.PositiveIntegerField()
    reason=models.CharField(max_length=150)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,editable=False)
    created_at=models.DateTimeField(auto_now_add=True)

class WelcomeClaim(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    email=models.CharField(max_length=254,unique=True,null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
