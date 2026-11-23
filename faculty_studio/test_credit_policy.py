import json,uuid
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from .core import *
from .models import WelcomeClaim

class CreditPolicyTests(TestCase):
    def setUp(self):
        cache.clear();self.user=get_user_model().objects.create_user('existing',email='existing@example.com',password='LongPassword123!');self.admin=get_user_model().objects.create_superuser('boss','boss@example.com','LongPassword123!');self.wallet=allowed_wallet(self.user)
        self.chapter=Chapter.objects.create(subject='physics',level=12,name='Atoms');self.topic=Subtopic.objects.create(chapter=self.chapter,name='Energy')
        self.q=[Question.objects.create(subtopic=self.topic,difficulty='easy',correct_option=2,question_kind='mcq',fingerprint=str(uuid.uuid4()),structured={'stem':'Q','options':['A','B','C','D'],'diagrams':[]}) for i in range(20)]
    def register(self,email='new@example.com',username='newteacher'):
        return self.client.post('/studio/api/register/',json.dumps({'name':'New Teacher','username':username,'email':email,'password':'NewPassword123!'}),content_type='application/json')
    def attempt(self,ids):
        t=Practice.objects.create(owner=self.user,question_ids=ids,answer_key={str(i):2 for i in ids})
        return reward_attempt(self.user,t.pk,{str(i):2 for i in ids})
    def test_new_account_50_once(self):
        r=self.register();self.assertEqual(r.status_code,200,r.content);u=get_user_model().objects.get(username='newteacher');self.assertEqual(balance(allowed_wallet(u)),50);self.assertFalse(award_welcome(u));self.assertEqual(balance(allowed_wallet(u)),50)
    def test_required_email(self):self.assertEqual(self.register('').status_code,400)
    def test_case_insensitive_existing_email(self):self.assertEqual(self.register(' EXISTING@EXAMPLE.COM ').status_code,400)
    def test_new_email_normalized(self):
        self.assertEqual(self.register(' New@Example.COM ').status_code,200);self.assertEqual(self.register('new@example.com','anothername').status_code,400);self.assertEqual(WelcomeClaim.objects.count(),1)
    def test_username_conflict_rolls_back(self):
        self.assertEqual(self.register(username='existing').status_code,400);self.assertEqual(WelcomeClaim.objects.count(),0);self.assertEqual(Grant.objects.count(),0)
    def test_existing_welcome_and_rerun(self):
        self.assertTrue(award_welcome(self.user));self.assertFalse(award_welcome(self.user));self.assertEqual(balance(self.wallet),50)
    def test_claim_retained_if_email_changes(self):
        award_welcome(self.user);self.user.email='changed@example.com';self.user.save();self.assertEqual(self.register('existing@example.com').status_code,400)
    def test_three_plus_two_carries(self):
        self.assertEqual(self.attempt([q.pk for q in self.q[:3]]).reward,0);self.assertEqual(Profile.objects.get(user=self.user).practice_progress,3)
        self.assertEqual(self.attempt([q.pk for q in self.q[3:5]]).reward,1);self.assertEqual(balance(self.wallet),1)
    def test_repeated_questions_and_submission(self):
        ids=[q.pk for q in self.q[:5]];a=self.attempt(ids);self.assertEqual(a.reward,1);self.assertEqual(reward_attempt(self.user,a.pk,{}).reward,1);self.assertEqual(self.attempt(ids).reward,0);self.assertEqual(balance(self.wallet),1)
    def test_daily_cap(self):
        p=Policy.current();p.practice_daily_cap=2;p.save();self.assertEqual(self.attempt([q.pk for q in self.q]).reward,2);self.assertEqual(balance(self.wallet),2)
    def test_adjust_positive_negative_idempotent(self):
        self.assertTrue(adjust_wallet(self.wallet,self.admin,50,'Support','adjust:1'));self.assertFalse(adjust_wallet(self.wallet,self.admin,50,'Support','adjust:1'));adjust_wallet(self.wallet,self.admin,-12,'Correction','adjust:2');self.assertEqual(balance(self.wallet),38);self.assertEqual(Ledger.objects.count(),2)
    def test_insufficient_adjustment_rolls_back(self):
        with self.assertRaises(ValueError):adjust_wallet(self.wallet,self.admin,-1,'Correction','adjust:0')
        self.assertEqual(Ledger.objects.count(),0)
    def test_admin_adjustment_permissions_and_form(self):
        url=reverse('admin:faculty_studio_wallet_adjust',args=[self.wallet.pk]);self.user.is_staff=True;self.user.save();self.client.force_login(self.user);self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_login(self.admin);self.assertContains(self.client.get(url),'Credits to add or deduct');ref=str(uuid.uuid4());data={'amount':50,'reason':'Welcome support','reference':ref};self.assertEqual(self.client.post(url,data).status_code,302);self.assertEqual(self.client.post(url,data).status_code,302);self.assertEqual(balance(self.wallet),50)
    def test_anonymous_dashboard_cannot_claim(self):
        self.assertEqual(self.client.get('/studio/api/dashboard/').status_code,401);self.assertEqual(WelcomeClaim.objects.count(),0)

    def test_invalid_email(self):self.assertEqual(self.register('not-an-email').status_code,400)
    def test_existing_account_command_idempotent(self):
        from django.core.management import call_command
        from io import StringIO
        out=StringIO();call_command('award_welcome',username='existing',stdout=out);call_command('award_welcome',username='existing',stdout=out)
        self.assertEqual(balance(self.wallet),50);self.assertEqual(WelcomeClaim.objects.count(),1)
