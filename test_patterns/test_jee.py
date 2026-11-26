from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
import json
from question_bank.models import Chapter, Subtopic, Question
from .core import validate_spec, choose_section, JEE_SECTIONS
from .models import TestPlan
from .exporting import prepare_export

class JeePracticeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.scopes = {}
        for subject in (*JEE_SECTIONS, 'biology'):
            ch = Chapter.objects.create(subject=subject, level=11, name='Fixture '+subject)
            t = Subtopic.objects.create(chapter=ch, name='Practice')
            cls.scopes[subject] = {'chapters':[ch.pk], 'topics':[t.pk]}
            Question.objects.bulk_create([Question(subtopic=t, difficulty='moderate', correct_option=1, active=True, fingerprint=f'jee-fixture-{subject}-{i}', structured={'stem':f'Fixture {subject} {i}', 'options':['1','2','3','4'], 'hint':'Fixture', 'diagrams':[]}) for i in range(30)])

    def data(self, profile, **extra):
        return {'profile':profile, 'subject':'pcm', 'sections':{k:self.scopes[k] for k in JEE_SECTIONS}, **extra}

    def test_fixed_profiles_and_export(self):
        for profile, count in [('jee30',10),('jee45',15),('jee60',20),('jee75',25)]:
            spec = validate_spec(self.data(profile))
            self.assertEqual(spec['targets'],dict.fromkeys(JEE_SECTIONS,count))
            self.assertEqual(spec['marks'],count*12)
            picked = [row[0] for section in JEE_SECTIONS for row in choose_section(spec,section)]
            self.assertEqual(len(set(picked)),count*3)
            plan=TestPlan.objects.create(profile=profile,specification=spec)
            req=RequestFactory().post('/',{'test_pattern_id':str(plan.pk),'exam':'jee'})
            details, groups=prepare_export(req,{'start_number':1},picked,Question.objects.select_related('subtopic__chapter').in_bulk(picked),[])
            self.assertEqual([(label,len(rows)) for label,rows in groups],[('Physics',count),('Chemistry',count),('Mathematics',count)])
            self.assertEqual(details['marks'],count*12)

    def test_custom_and_cumulative(self):
        targets={'physics':0,'chemistry':3,'mathematics':7}
        for profile in ('jeecustom','jeecumulative'):
            spec=validate_spec(self.data(profile,targets=targets))
            self.assertEqual(spec['targets'],{'chemistry':3,'mathematics':7})
            self.assertEqual(spec['total'],10)

    def test_reject_biology_and_invalid_counts(self):
        for data in [self.data('jee30',subject='biology'),self.data('jee30',sections=self.scopes), self.data('jee30',sections={**self.scopes, 'mathematics':self.scopes['biology']}),self.data('jeecustom',targets=dict.fromkeys(JEE_SECTIONS,0)),self.data('jeecustom',targets=dict.fromkeys(JEE_SECTIONS,101)),self.data('jeecustom',targets=dict.fromkeys(JEE_SECTIONS,True))]:
            with self.assertRaises(ValueError):validate_spec(data)
        row=Question.objects.filter(subtopic__chapter__subject='biology').first()
        with self.assertRaises(ValueError):prepare_export(RequestFactory().post('/',{'exam':'jee'}),{},[row.pk],{row.pk:row},[])

    def test_generate_replace_and_examination_guard(self):
        self.client.force_login(get_user_model().objects.create_user('jee-pattern-tester'))
        response = self.client.post(reverse('test_patterns:generate'), json.dumps(self.data('jee30', exam='jee')), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        self.assertEqual(result['total'], 30)
        self.assertEqual(result['marks'], 120)
        self.assertEqual([q['section'] for q in result['questions']], [section for section in JEE_SECTIONS for _ in range(10)])
        chosen = [q['id'] for q in result['questions']]
        replacement = self.client.post(reverse('test_patterns:replace'), json.dumps({'plan_id':result['plan_id'], 'section':'mathematics', 'exclude':chosen}), content_type='application/json')
        self.assertEqual(replacement.status_code, 200, replacement.content)
        self.assertEqual(replacement.json()['question']['section'], 'mathematics')
        self.assertNotIn(replacement.json()['question']['id'], chosen)
        for bad in (self.data('jee30', exam='neet'), {'profile':'custom40','subject':'mathematics','exam':'neet'}, {'profile':'custom40','subject':'physics','exam':'jee'}):
            with self.assertRaises(ValueError): validate_spec(bad)
        with self.assertRaises(ValueError):
            prepare_export(RequestFactory().post('/',{'exam':'neet','test_pattern_id':result['plan_id']}),{},chosen,Question.objects.select_related('subtopic__chapter').in_bulk(chosen),[])

    def test_shortage_cannot_substitute_another_subject(self):
        spec = validate_spec(self.data('jee75'))
        Question.objects.filter(subtopic__chapter__subject='mathematics').update(active=False)
        with self.assertRaisesRegex(ValueError, 'Mathematics needs 25'):
            choose_section(spec, 'mathematics')
