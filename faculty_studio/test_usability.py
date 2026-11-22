import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from question_bank.models import Question,Chapter,Subtopic
from faculty_studio.core import validate
from faculty_studio.models import Pattern,Draft

class UsabilityTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('teacher2',password='GoodTeacherPassword42!');self.client.force_login(self.user)
        self.chapters=[];self.topics=[]
        for i in range(3):
            ch=Chapter.objects.create(subject='physics',level=11,name='Chapter '+str(i));self.chapters.append(ch.pk);t=Subtopic.objects.create(chapter=ch,name='Topic '+str(i));self.topics.append(t.pk)
            Question.objects.bulk_create([Question(subtopic=t,difficulty='easy',correct_option=1,question_kind='mcq',question_visual='diagram',structured={'stem':'Diagram '+str(i)+' '+str(j),'options':['A','B','C','D'],'hint':'','diagrams':[]},fingerprint='browse-'+str(i)+'-'+str(j)) for j in range(14)])
    def post(self,action,data):return self.client.post('/studio/api/'+action+'/',json.dumps(data),content_type='application/json')
    def spec(self,chapters=None,label='Physics'):
        return {'sections':[{'label':label,'subject':'physics','chapters':chapters or [],'topics':[],'slots':['any']*10,'difficulty':''}]}
    def test_save_structure_without_chapters(self):
        r=self.post('pattern-save',{'name':'My sequence','spec':self.spec()});self.assertEqual(r.status_code,200,r.content);self.assertEqual(Pattern.objects.get().spec['sections'][0]['chapters'],[])
    def test_missing_label_is_derived_from_subject(self):
        r=self.post('pattern-save',{'name':'Blank label fixed','spec':self.spec(label='')});self.assertEqual(r.status_code,200);self.assertEqual(r.json()['spec']['sections'][0]['label'],'Physics')
    def test_generate_still_requires_scope(self):
        r=self.post('generate',{'spec':self.spec()});self.assertEqual(r.status_code,400);self.assertIn('Physics',r.json()['error']);self.assertIn('chapters',r.json()['error']);self.assertFalse(Draft.objects.exists())
    def test_saved_pattern_then_select_scope_and_generate(self):
        p=self.post('pattern-save',{'name':'Reusable','spec':self.spec()}).json();s=p['spec'];s['sections'][0]['chapters']=self.chapters
        r=self.post('generate',{'name':'Reusable','spec':s});self.assertEqual(r.status_code,200,r.content);self.assertEqual(len(set(r.json()['question_ids'])),10)
    def token(self):
        r=self.client.post('/api/mobile/v1/login/',json.dumps({'username':'teacher2','password':'GoodTeacherPassword42!'}),content_type='application/json');return r.json()['token']
    def test_all_chapters_diagram_browsing_reaches_last_page(self):
        token=self.token();ids=[];positions=[]
        for page in range(1,8):
            r=self.client.get('/api/mobile/v1/browse/',{'subject':'physics','difficulty':'','question_type':'diagram','chapters':self.chapters,'topics':self.topics,'page_size':'6','page':page},HTTP_AUTHORIZATION='Bearer '+token)
            self.assertEqual(r.status_code,200,r.content);d=r.json();self.assertEqual(d['count'],42);self.assertEqual(d['pages'],7);self.assertEqual(d['page_size'],6);self.assertEqual(len(d['questions']),6);ids += [q['id'] for q in d['questions']];positions.append(d['page'])
        self.assertEqual(len(set(ids)),42);self.assertEqual(positions,list(range(1,8)));self.assertEqual(set(ids),set(Question.objects.values_list('pk',flat=True)))
    def test_default_page_size_remains_compatible(self):
        r=self.client.get('/api/mobile/v1/browse/',{'subject':'physics','chapters':self.chapters,'topics':self.topics},HTTP_AUTHORIZATION='Bearer '+self.token());self.assertEqual(r.status_code,200);self.assertEqual(len(r.json()['questions']),12)
    def test_invalid_page_size_rejected(self):
        r=self.client.get('/api/mobile/v1/browse/',{'subject':'physics','chapters':self.chapters,'topics':self.topics,'page_size':'100000'},HTTP_AUTHORIZATION='Bearer '+self.token());self.assertEqual(r.status_code,400)
    def test_saved_patterns_remain_private(self):
        self.post('pattern-save',{'name':'Private','spec':self.spec()});other=get_user_model().objects.create_user('other2');self.client.force_login(other);self.assertEqual(self.client.get('/studio/api/patterns/').json()['patterns'],[])
