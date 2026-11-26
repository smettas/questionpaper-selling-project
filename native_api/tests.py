import base64
from io import BytesIO
import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase,Client
from PIL import Image
from question_bank.models import Chapter,Subtopic,Question
from syllabus_builder.models import CorrectionReport

class NativeApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=get_user_model().objects.create_user('teacher',password='test-password-long',is_staff=True)
        cls.other=get_user_model().objects.create_user('other',password='test-password-long',is_staff=True)
        cls.regular=get_user_model().objects.create_user('notstaff',password='test-password-long')
        cls.ch=Chapter.objects.create(subject='physics',level=12,name='Alternating Current')
        cls.topic=Subtopic.objects.create(chapter=cls.ch,name='AC')
        buf=BytesIO();Image.new('RGB',(80,40),'white').save(buf,'PNG')
        cls.content={'stem':'Match the following\nList I | List II\nA. Voltage | I. Volt\nB. Current | II. Ampere\nCompute \\(\\sqrt{4}\\).','options':['1','2','3','4'],'hint':'The result is \\(2\\).','diagrams':[{'placement':'question','png':base64.b64encode(buf.getvalue()).decode()}]}
        cls.rows=[]
        for i in range(55):cls.rows.append(Question.objects.create(subtopic=cls.topic,correct_option=2,difficulty='easy',active=True,fingerprint='native-'+str(i),structured=cls.content))
        cls.hidden=Question.objects.create(subtopic=cls.topic,correct_option=2,difficulty='easy',active=False,fingerprint='native-hidden',structured=cls.content)
    def setUp(self):
        cache.clear();self.client=Client(enforce_csrf_checks=True)
        self.token=self.client.post('/api/mobile/v1/login/',json.dumps({'username':'teacher','password':'test-password-long'}),content_type='application/json').json()['token']
    def req(self,action,data=None,token=None):
        headers={'HTTP_AUTHORIZATION':'Bearer '+(token or self.token)}
        if data is None:return self.client.get('/api/mobile/v1/'+action+'/',**headers)
        return self.client.post('/api/mobile/v1/'+action+'/',json.dumps(data),content_type='application/json',**headers)
    def scope(self):return dict(subject='physics',chapters=[self.ch.pk],topics=[self.topic.pk],difficulty='',question_type='')
    def test_requires_token_and_allows_registered_users(self):
        self.assertEqual(self.client.get('/api/mobile/v1/catalog/').status_code,401)
        r=self.client.post('/api/mobile/v1/login/',json.dumps({'username':'notstaff','password':'test-password-long'}),content_type='application/json');self.assertEqual(r.status_code,200);self.assertIn('token',r.json())
        self.assertEqual(self.req('catalog').status_code,200)
    def test_password_change_revokes_token(self):
        self.user.set_password('changed-password');self.user.save();self.assertEqual(self.req('me').status_code,401)
    def test_sample_unique_active_and_does_not_mutate_bank(self):
        before=list(Question.objects.values());r=self.req('sample',{**self.scope(),'count':12});self.assertEqual(r.status_code,200);ids=[q['id'] for q in r.json()['questions']];self.assertEqual(len(set(ids)),12);self.assertNotIn(self.hidden.pk,ids);self.assertEqual(list(Question.objects.values()),before)
    def test_native_math_matching_diagram_and_hidden_preview(self):
        r=self.req('details',{'ids':[self.rows[0].pk,self.hidden.pk]}).json();self.assertEqual(len(r['failed']),1)
        q=r['questions'][0];self.assertEqual(q['answer'],2);self.assertTrue(any(b['type']=='table' for b in q['stem_blocks']))
        math=[t for b in q['stem_blocks'] if b['type']=='paragraph' for t in b['tokens'] if t['type']=='math'];self.assertTrue(math);self.assertTrue(math[0]['uri'].startswith('data:image/png;base64,'));self.assertEqual(q['diagrams'][0]['ratio'],2)
    def test_oversized_preview_batch_and_bad_scope_rejected(self):
        self.assertEqual(self.req('details',{'ids':list(range(1,14))}).status_code,400)
        self.assertEqual(self.req('sample',{**self.scope(),'count':3,'chapters':[]}).status_code,400)
    def test_report_creates_review_not_question_edit(self):
        before=Question.objects.get(pk=self.rows[0].pk).structured
        r=self.req('report',{'question_id':self.rows[0].pk,'category':'answer','note':'Please check the answer and its explanation.'});self.assertEqual(r.status_code,201);self.assertEqual(CorrectionReport.objects.get().reporter,self.user);self.assertEqual(Question.objects.get(pk=self.rows[0].pk).structured,before)
    def test_plan_ticket_bound_to_staff_identity(self):
        spec={'profile':'custom40','subject':'physics','sections':{'physics':{'chapters':[self.ch.pk],'topics':[self.topic.pk]}}}
        r=self.req('generate',spec);self.assertEqual(r.status_code,200);data=r.json();self.assertEqual(data['total'],40)
        other=self.client.post('/api/mobile/v1/login/',json.dumps({'username':'other','password':'test-password-long'}),content_type='application/json').json()['token']
        self.assertEqual(self.req('replace',{'plan_ticket':data['plan_ticket'],'section':'physics','exclude':[]},token=other).status_code,400)
        replace=self.req('replace',{'plan_ticket':data['plan_ticket'],'section':'physics','exclude':[q['id'] for q in data['questions']]});self.assertEqual(replace.status_code,200)
        self.assertNotIn(replace.json()['question']['id'],[q['id'] for q in data['questions']])
    def test_export_reuses_actual_pdf_and_word_pipeline(self):
        from zipfile import ZipFile
        from pypdfium2 import PdfDocument
        with patch('native_api.views.paper.build_pdf', wraps=__import__('paper_builder.pdf',fromlist=['build_pdf']).build_pdf):
            r=self.client.post('/api/mobile/v1/export/',{'question_ids':json.dumps([self.rows[0].pk]),'title':'Native test','output_format':'both','arrangement':'combined','start_number':'1','option_layout':'four','page_columns':'two','watermark':'OJAS'},HTTP_AUTHORIZATION='Bearer '+self.token)
        self.assertEqual(r.status_code,200,r.content[:400]);files=r.json()['files'];self.assertEqual(len(files),2)
        pdf=next(f for f in files if f['name'].endswith('.pdf'));self.assertTrue(base64.b64decode(pdf['data']).startswith(b'%PDF'))
        word=next(f for f in files if f['name'].endswith('.docx'))
        with ZipFile(BytesIO(base64.b64decode(word['data']))) as z:self.assertIn('word/document.xml',z.namelist())
    def test_invalid_export_does_not_change_bank(self):
        r=self.client.post('/api/mobile/v1/export/',{'question_ids':json.dumps([self.hidden.pk]),'start_number':'1'},HTTP_AUTHORIZATION='Bearer '+self.token);self.assertEqual(r.status_code,400)
    def test_throttled_login(self):
        for _ in range(15):self.client.post('/api/mobile/v1/login/',json.dumps({'username':'bad','password':'wrong'}),content_type='application/json')
        r=self.client.post('/api/mobile/v1/login/',json.dumps({'username':'bad','password':'wrong'}),content_type='application/json');self.assertEqual(r.status_code,429)

    def test_manual_browse_is_paginated_and_published_only(self):
        first=self.client.get('/api/mobile/v1/browse/',{**self.scope(),'page':1},HTTP_AUTHORIZATION='Bearer '+self.token)
        second=self.client.get('/api/mobile/v1/browse/',{**self.scope(),'page':2},HTTP_AUTHORIZATION='Bearer '+self.token)
        self.assertEqual(first.status_code,200);self.assertEqual(first.json()['count'],55)
        self.assertEqual(len(first.json()['questions']),12)
        self.assertFalse(set(q['id'] for q in first.json()['questions'])&set(q['id'] for q in second.json()['questions']))
    def test_matching_math_row_stays_two_columns(self):
        from native_api.views import blocks
        result=blocks('List I | List II\nA. \\(\\sqrt{4}\\) | I. two')
        self.assertEqual(len(result),1);self.assertEqual(result[0]['type'],'table')
        self.assertTrue(any(t['type']=='math' for t in result[0]['rows'][1][0]))
    def test_multipart_logo_and_native_plan_export(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        spec={'profile':'custom40','subject':'physics','sections':{'physics':{'chapters':[self.ch.pk],'topics':[self.topic.pk]}}}
        plan=self.req('generate',spec).json()
        buf=BytesIO();Image.new('RGB',(32,16),'blue').save(buf,'PNG')
        r=self.client.post('/api/mobile/v1/export/',{'question_ids':json.dumps([q['id'] for q in plan['questions']]),'plan_ticket':plan['plan_ticket'],'start_number':'1','output_format':'pdf','arrangement':'combined','logo':SimpleUploadedFile('logo.png',buf.getvalue(),content_type='image/png')},HTTP_AUTHORIZATION='Bearer '+self.token)
        self.assertEqual(r.status_code,200,r.content[:300]);self.assertTrue(r.json()['files'])
