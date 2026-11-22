import json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,RequestFactory,Client,override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from django.http import JsonResponse,HttpResponse
from question_bank.models import Chapter,Subtopic,Question
from .models import *
from .core import *
from .exporting import meter_export

@override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.InMemoryStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class StudioTests(TestCase):
    def setUp(self):
        cache.clear();self.user=get_user_model().objects.create_user('teacher',password='SomeLongPassword42!');self.other=get_user_model().objects.create_user('another',password='AnotherLongPassword42!')
        self.client.force_login(self.user);self.chapter=Chapter.objects.create(subject='physics',level=12,name='Atoms');self.topic=Subtopic.objects.create(chapter=self.chapter,name='Energy levels')
        self.q=[]
        for k in ['mcq']*8+['assertion-reason']*3+['statement']*3+['matching']*3:
            i=len(self.q);self.q.append(Question.objects.create(subtopic=self.topic,difficulty='easy',correct_option=2,question_kind=k,fingerprint='fp'+str(i),structured={'diagrams':[],'type':k,'stem':'Question '+str(i),'options':['A','B','C','D'],'hint':'Reason'}))
        self.wallet=allowed_wallet(self.user)
    def spec(self,slots=None):return {'sections':[{'label':'Physics','subject':'physics','chapters':[self.chapter.pk],'topics':[],'difficulty':'','slots':slots or ['mcq']*5+['assertion-reason','statement','matching']}]}
    def post(self,action,data):return self.client.post('/studio/api/'+action+'/',json.dumps(data),content_type='application/json')
    def fund(self,n=100):credit(self.wallet,self.user,n,'Test funding','fund:'+str(Grant.objects.count()))
    def test_registration_nonstaff_hashed_password(self):
        self.client.logout();r=self.post('register',{'username':'newteacher','name':'New Teacher','academy':'OJAS','password':'SecretLongValue42!'})
        self.assertEqual(r.status_code,200);u=get_user_model().objects.get(username='newteacher');self.assertFalse(u.is_staff);self.assertTrue(u.check_password('SecretLongValue42!'));self.assertEqual(self.client.get('/studio/api/dashboard/').status_code,200)
    def test_registration_weak_password_and_closed(self):
        self.assertEqual(self.post('register',{'username':'poor','name':'Poor Test','password':'123'}).status_code,400)
        p=Policy.current();p.registration_open=False;p.save();self.assertEqual(self.post('register',{'username':'validuser','name':'Valid User','password':'GoodLongValue42!'}).status_code,400)
    def test_native_nonstaff_token(self):
        r=self.client.post('/api/mobile/v1/login/',json.dumps({'username':'teacher','password':'SomeLongPassword42!'}),content_type='application/json');self.assertEqual(r.status_code,200)
        token=r.json()['token'];self.client.logout();self.assertEqual(self.client.get('/api/mobile/v1/studio-dashboard/',HTTP_AUTHORIZATION='Bearer '+token).status_code,200)
        self.user.set_password('ChangedLongPassword42!');self.user.save();self.assertEqual(self.client.get('/api/mobile/v1/studio-dashboard/',HTTP_AUTHORIZATION='Bearer '+token).status_code,401)
    def test_anonymous_gate(self):
        self.client.logout();self.assertEqual(self.client.get('/').status_code,302);self.assertEqual(self.client.post('/download/').status_code,401);self.assertEqual(self.client.get('/studio/').status_code,200)
    def test_exact_slot_positions(self):
        r=self.post('generate',{'spec':self.spec()});self.assertEqual(r.status_code,200);ids=r.json()['question_ids'];self.assertEqual(len(set(ids)),8)
        rows=Question.objects.in_bulk(ids);self.assertEqual([rows[x].question_kind for x in ids],self.spec()['sections'][0]['slots'])
    def test_overlapping_any_and_rare(self):
        spec=validate(self.spec(['any']*15+['matching']*2));self.assertEqual(len(set(allocate(spec))),17)
    def test_unavailable_type_no_draft(self):
        r=self.post('generate',{'spec':self.spec(['graph'])});self.assertEqual(r.status_code,400);self.assertEqual(Draft.objects.count(),0)
    def test_invalid_scope_and_total(self):
        s=self.spec();s['sections'][0]['subject']='chemistry';self.assertEqual(self.post('generate',{'spec':s}).status_code,400)
        s=self.spec(['mcq']*301);self.assertEqual(self.post('pattern-save',{'name':'Invalid','spec':s}).status_code,400)
    def test_pattern_owner(self):
        p=self.post('pattern-save',{'name':'Mine','spec':self.spec()}).json();self.client.force_login(self.other)
        self.assertEqual(self.client.get('/studio/api/patterns/').json()['patterns'],[])
        self.assertEqual(self.post('pattern-save',{'id':p['id'],'name':'Stolen','spec':self.spec()}).status_code,404)
    def test_replacement_owns_same_type(self):
        d=self.post('generate',{'spec':self.spec()}).json();old=d['question_ids'][5];r=self.post('replace',{'draft_id':d['id'],'position':5});self.assertEqual(r.status_code,200);pk=r.json()['question_ids'][5];self.assertNotEqual(pk,old);self.assertEqual(Question.objects.get(pk=pk).question_kind,'assertion-reason')
        self.client.force_login(self.other);self.assertEqual(self.post('replace',{'draft_id':d['id'],'position':5}).status_code,404)
    def test_no_replacement_preserves_old(self):
        d=self.post('generate',{'spec':self.spec(['matching']*3)}).json();self.assertEqual(self.post('replace',{'draft_id':d['id'],'position':0}).status_code,400);self.assertEqual(Draft.objects.get(pk=d['id']).question_ids,d['question_ids'])
    def test_practice_answers_hidden(self):
        t=self.post('practice-start',{'spec':self.spec()}).json();v=self.client.get('/studio/api/practice-view/',{'id':t['id']}).json();self.assertNotIn('answer',v['question']);self.assertNotIn('hint_blocks',v['question'])
    def test_reward_once_and_submission_idempotent(self):
        t=self.post('practice-start',{'spec':self.spec()}).json();obj=Practice.objects.get(pk=t['id']);answers={str(pk):2 for pk in obj.question_ids}
        r=self.post('practice-submit',{'id':t['id'],'answers':answers});self.assertEqual(r.json()['reward'],8);self.assertEqual(balance(self.wallet),8)
        self.assertEqual(self.post('practice-submit',{'id':t['id'],'answers':answers}).json()['reward'],8);self.assertEqual(balance(self.wallet),8)
        t2=self.post('practice-start',{'spec':self.spec()}).json();o2=Practice.objects.get(pk=t2['id']);self.post('practice-submit',{'id':t2['id'],'answers':{str(pk):2 for pk in o2.question_ids}});self.assertEqual(balance(self.wallet),len(RewardedQuestion.objects.filter(owner=self.user)))
    def test_reward_daily_cap(self):
        p=Policy.current();p.practice_daily_cap=3;p.save();t=self.post('practice-start',{'spec':self.spec()}).json();o=Practice.objects.get(pk=t['id']);r=self.post('practice-submit',{'id':t['id'],'answers':{str(pk):2 for pk in o.question_ids}});self.assertEqual(r.json()['reward'],3)
    def test_other_user_cannot_submit_practice(self):
        t=self.post('practice-start',{'spec':self.spec()}).json();self.client.force_login(self.other);self.assertEqual(self.post('practice-submit',{'id':t['id'],'answers':{}}).status_code,400)
    def test_credit_expiry_and_idempotency(self):
        self.fund();credit(self.wallet,self.user,100,'Again','fund:0');self.assertEqual(balance(self.wallet),100)
        Grant.objects.update(expires_at=timezone.now()-timedelta(seconds=1));self.assertEqual(balance(self.wallet),0)
    def test_institution_wallet_permission(self):
        org=Institution.objects.create(name='Academy');Profile.objects.create(user=self.user,institution=org);w=allowed_wallet(self.user,org.pk);self.assertEqual(w.institution,org)
        with self.assertRaises(ValueError):allowed_wallet(self.other,org.pk)
    def test_recharge_pending_no_money_creation(self):
        r=self.post('recharge',{'rupees':100,'reference':'payment-12345'});self.assertEqual(r.status_code,200);self.assertEqual(Recharge.objects.get().credits,1000);self.assertEqual(balance(self.wallet),0)
    def export_request(self,**extra):
        req=RequestFactory().post('/download/',{'question_ids':json.dumps([self.q[0].pk]),'title':'Test','studio_expected_cost':'1',**extra});req.user=self.user;return req
    def test_paid_export_only_once(self):
        self.fund();calls=[]
        @meter_export
        def view(r):calls.append(1);return JsonResponse({'files':[{'name':'paper.pdf','type':'application/pdf','data':'YQ=='}]})
        a=view(self.export_request());b=view(self.export_request());self.assertEqual(a.status_code,200);self.assertEqual(b.status_code,200);self.assertEqual(len(calls),1);self.assertEqual(balance(self.wallet),99);self.assertEqual(Paper.objects.count(),1)
    def test_render_failure_no_charge(self):
        self.fund();response=meter_export(lambda r:HttpResponse('Cannot render',status=400))(self.export_request());self.assertEqual(response.status_code,400);self.assertEqual(balance(self.wallet),100);self.assertFalse(Paper.objects.exists())
    def test_insufficient_and_stale_quote(self):
        response=meter_export(lambda r:JsonResponse({'files':[1]}))(self.export_request());self.assertEqual(response.status_code,400);self.assertFalse(Paper.objects.exists())
        self.fund();self.assertEqual(meter_export(lambda r:JsonResponse({'files':[1]}))(self.export_request(studio_expected_cost='2')).status_code,400)
    def test_atomic_rollback_if_balance_changes(self):
        self.fund(1)
        def renderer(r):Grant.objects.update(remaining=0);return JsonResponse({'files':[{'name':'x.pdf','type':'application/pdf','data':'eA=='}]})
        r=meter_export(renderer)(self.export_request());self.assertEqual(r.status_code,400);self.assertFalse(Paper.objects.exists())
    def test_real_pattern_pdf_word_export(self):
        self.fund();d=self.post('generate',{'name':'Position pattern','spec':self.spec()}).json();r=self.client.post('/download/',{'question_ids':json.dumps(d['question_ids']),'studio_draft_id':d['id'],'studio_expected_cost':'8','title':'Faculty paper','institution':'OJAS','arrangement':'combined','output_format':'both','page_columns':'two','option_layout':'four','start_number':'1','marks':'32'})
        self.assertEqual(r.status_code,200,r.content[:300]);self.assertEqual(len(r.json()['files']),2);self.assertEqual(balance(self.wallet),92)
        r2=self.client.post('/download/',{'question_ids':json.dumps(d['question_ids'][::-1]),'studio_draft_id':d['id'],'studio_expected_cost':'8'});self.assertEqual(r2.status_code,400)
    def test_dashboard_and_saved_files_private(self):
        self.fund();r=meter_export(lambda r:JsonResponse({'files':[{'name':'x.pdf','type':'application/pdf','data':'eA=='}]}))(self.export_request());pid=json.loads(r.content)['paper_id'];self.client.force_login(self.other);self.assertEqual(self.client.get('/studio/api/paper-files/',{'id':pid}).status_code,404)
    def test_csrf_required_on_web_accounts(self):
        c=Client(enforce_csrf_checks=True);self.assertEqual(c.post('/studio/api/login/',json.dumps({'username':'teacher','password':'SomeLongPassword42!'}),content_type='application/json').status_code,403)
    def test_recharge_admin_approval_idempotent(self):
        from .admin import RechargeAdmin
        from django.contrib.admin.sites import AdminSite
        self.post('recharge',{'rupees':100,'reference':'verified-payment'})
        admin_user=get_user_model().objects.create_superuser('boss','boss@example.com','VeryLongBossPassword42!')
        req=RequestFactory().post('/admin/');req.user=admin_user
        a=RechargeAdmin(Recharge,AdminSite())
        with patch.object(a,'message_user'):
            a.approve(req,Recharge.objects.all());a.approve(req,Recharge.objects.all())
        self.assertEqual(balance(self.wallet),1000);self.assertEqual(Grant.objects.count(),1)
    def test_storage_failure_does_not_charge(self):
        self.fund()
        with patch('faculty_studio.exporting.default_storage.save',side_effect=OSError('Storage unavailable')):
            r=meter_export(lambda r:JsonResponse({'files':[{'name':'x.pdf','type':'application/pdf','data':'eA=='}]}))(self.export_request())
        self.assertEqual(r.status_code,400);self.assertEqual(balance(self.wallet),100);self.assertFalse(Paper.objects.exists())
    def test_expired_and_live_grants_spent_in_order(self):
        self.fund(5);credit(self.wallet,self.user,10,'Second','second');first=Grant.objects.order_by('pk').first()
        with transaction.atomic():debit_locked(self.wallet,self.user,6,'spend:test')
        first.refresh_from_db();self.assertEqual(first.remaining,0);self.assertEqual(balance(self.wallet),9)
    def test_two_biology_sections_have_separate_positions(self):
        c=Chapter.objects.create(subject='biology',level=11,name='Botany bank');t=Subtopic.objects.create(chapter=c,name='Plants')
        for i in range(4):Question.objects.create(subtopic=t,difficulty='easy',correct_option=1,structured={'type':'mcq','stem':str(i),'options':['A','B','C','D'],'hint':'ok','diagrams':[]},fingerprint='bio'+str(i))
        a={'label':'Botany','subject':'biology','chapters':[c.pk],'topics':[],'difficulty':'','slots':['mcq']*2};b={**a,'label':'Zoology'}
        r=self.post('generate',{'spec':{'sections':[a,b]}});self.assertEqual(r.status_code,200);self.assertEqual(len(set(r.json()['question_ids'])),4)
    def test_case_repeat_exact_download_no_extra_debit(self):
        self.fund();r=meter_export(lambda r:JsonResponse({'files':[{'name':'x.pdf','type':'application/pdf','data':'eA=='}]}))(self.export_request());pid=json.loads(r.content)['paper_id']
        saved=self.client.get('/studio/api/paper-files/',{'id':pid});self.assertEqual(saved.status_code,200);self.assertEqual(saved.json()['files'][0]['data'],'eA==');self.assertEqual(balance(self.wallet),99)
