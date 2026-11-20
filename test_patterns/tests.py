import json
from base64 import b64decode
from io import BytesIO
from unittest.mock import patch
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from question_bank.models import Chapter, Subtopic, Question
from question_bank.chapter_order import CHAPTERS
from .core import validate_spec, choose_section, available_catalog, missing_chapters, suggestion, LABELS
from .models import TestPlan
from .exporting import prepare_export


class PatternTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.groups={}
        definitions={'physics':('physics','Motion in a Straight Line'),'chemistry':('chemistry','Equilibrium'),
                     'botany':('biology','Plant Kingdom'),'zoology':('biology','Animal Kingdom')}
        for section,(subject,name) in definitions.items():
            chapter=Chapter.objects.create(subject=subject,level=11,name=name)
            cls.groups[section]=chapter
            for j in range(2):
                topic=Subtopic.objects.create(chapter=chapter,name=f'Topic {j+1}')
                for i in range(35):
                    content={'stem':f'Question {section} {j} {i}: find the value.', 'options':['1','2','3','4'],
                             'hint':'Use the given relation.', 'diagrams':[]}
                    Question.objects.create(subtopic=topic,difficulty=['easy','moderate','hard'][i%3],correct_option=2,
                        structured=content,fingerprint=f'{section}-{j}-{i}')
        cls.config={'profile':'cumulative','confirm_biology':True,'sections':{
            section:{'chapters':[ch.pk],'topics':[]} for section,ch in cls.groups.items()}}

    def post(self,name,data):
        return self.client.post(reverse('test_patterns:'+name),json.dumps(data),content_type='application/json')

    def test_cumulative_180_720_and_45_each(self):
        response=self.post('generate',self.config)
        self.assertEqual(response.status_code,200,response.content)
        d=response.json();self.assertEqual(d['total'],180);self.assertEqual(d['marks'],720)
        self.assertEqual(len({q['id'] for q in d['questions']}),180)
        for section in LABELS:self.assertEqual(sum(q['section']==section for q in d['questions']),45)
        self.assertEqual([q['section'] for q in d['questions'][:45]],['physics']*45)
        self.assertEqual(TestPlan.objects.count(),1)

    def test_cumulative_includes_all_chapter_topics_even_when_client_sends_subset(self):
        spec=validate_spec(self.config)
        self.assertEqual(len(spec['sections']['physics']['topics']),2)
        ids={r[2] for r in choose_section(spec,'physics')}
        self.assertEqual(ids,set(spec['sections']['physics']['topics']))

    def test_custom40_single_subject_and_topic_exclusion(self):
        chapter=self.groups['physics'];topic=chapter.subtopic_set.first()
        # One topic contains 35; requesting 40 must fail without padding from topic 2.
        config={'profile':'custom40','subject':'physics','sections':{'physics':{'chapters':[chapter.pk],'topics':[topic.pk]}}}
        self.assertEqual(self.post('generate',config).status_code,400)
        config['sections']['physics']['topics']=list(chapter.subtopic_set.values_list('pk',flat=True))
        d=self.post('generate',config).json();self.assertEqual(d['total'],40);self.assertEqual(d['marks'],160)
        self.assertEqual({q['section'] for q in d['questions']},{'physics'})

    def test_custom40_all_sections_ten_each(self):
        config={**self.config,'profile':'custom40','subject':'all','sections':{
            k:{'chapters':[ch.pk],'topics':list(ch.subtopic_set.values_list('pk',flat=True))} for k,ch in self.groups.items()}}
        d=self.post('generate',config).json()
        self.assertEqual(d['total'],40)
        for section in LABELS:self.assertEqual(sum(q['section']==section for q in d['questions']),10)

    def test_biology_confirmation_and_no_overlap(self):
        self.assertEqual(self.post('generate',{**self.config,'confirm_biology':False}).status_code,400)
        config={**self.config,'sections':{**self.config['sections'],'zoology':self.config['sections']['botany']}}
        r=self.post('generate',config);self.assertEqual(r.status_code,400);self.assertIn('both Botany',r.json()['error'])

    def test_wrong_subject_unavailable_topic_and_shortage(self):
        config={**self.config,'sections':{**self.config['sections'],'physics':self.config['sections']['chemistry']}}
        self.assertEqual(self.post('generate',config).status_code,400)
        ch=self.groups['physics'];topic=self.groups['chemistry'].subtopic_set.first()
        config={'profile':'custom40','subject':'physics','sections':{'physics':{'chapters':[ch.pk],'topics':[topic.pk]}}}
        self.assertEqual(self.post('generate',config).status_code,400)
        Question.objects.filter(subtopic__chapter=ch).update(active=False)
        self.assertEqual(self.post('generate',self.config).status_code,400)

    def test_grand_blocks_missing_banks_and_catalog_lists_missing(self):
        r=self.post('generate',{**self.config,'profile':'grand'});self.assertEqual(r.status_code,400)
        self.assertIn('missing chapter banks',r.json()['error'])
        d=self.client.get(reverse('test_patterns:catalog')).json();self.assertIn('physics',d['missing'])
        self.assertEqual(suggestion({'subject':'biology','name':'Plant Kingdom'}),'botany')
        self.assertEqual(suggestion({'subject':'biology','name':'Animal Kingdom'}),'zoology')

    def test_full_grand_all_canonical_chapters(self):
        # Build a complete disposable catalog; full-syllabus mode then succeeds.
        groups={'physics':[],'chemistry':[],'botany':[],'zoology':[]}
        for (subject,level),names in CHAPTERS.items():
            for name in names:
                ch,_=Chapter.objects.get_or_create(subject=subject,level=level,name=name)
                section=suggestion({'subject':subject,'name':name});groups[section].append(ch.pk)
                topic,_=Subtopic.objects.get_or_create(chapter=ch,name='Grand topic')
                Question.objects.bulk_create([Question(subtopic=topic,difficulty='moderate',correct_option=1,
                    fingerprint=f'grand-{ch.pk}-{i}',structured={'stem':f'Find value {ch.pk} {i}.','options':['1','2','3','4'],'hint':'Reason.','diagrams':[]}) for i in range(5)])
        chapters,_=available_catalog();self.assertEqual(missing_chapters(chapters),{})
        r=self.post('generate',{'profile':'grand','confirm_biology':True,'sections':{
            k:{'chapters':v} for k,v in groups.items()}})
        self.assertEqual(r.status_code,200,r.content)
        d=r.json();self.assertEqual(len(d['questions']),180)
        for section,chapters in groups.items():
            self.assertEqual({q['chapter_id'] for q in d['questions'] if q['section']==section},set(chapters))

    def test_replace_is_same_section_new_id_and_full_preview(self):
        d=self.post('generate',self.config).json();old=d['questions'][0]
        r=self.post('replace',{'plan_id':d['plan_id'],'section':old['section'],'exclude':[q['id'] for q in d['questions']]})
        self.assertEqual(r.status_code,200,r.content);q=r.json()['question'];self.assertEqual(q['section'],old['section']);self.assertNotEqual(q['id'],old['id']);self.assertIsNotNone(q['preview'])

    def test_export_enforces_blueprint_splits_and_marks(self):
        d=self.post('generate',self.config).json();ids=[q['id'] for q in d['questions']]
        rows=Question.objects.select_related('subtopic__chapter').in_bulk(ids)
        request=RequestFactory().post('/download/',{'test_pattern_id':d['plan_id']})
        details,sections=prepare_export(request,{'marks':5,'start_number':1,'title':''},ids,rows,[])
        self.assertEqual(details['marks'],720);self.assertEqual([label for label,_ in sections],list(LABELS.values()))
        self.assertEqual(len(details['covered_chapters']),4)
        with self.assertRaises(ValueError):prepare_export(request,{'start_number':1},ids[:-1],rows,[])
        # Swap a Physics place for a different Chemistry item: 44/46 must fail.
        extra=Question.objects.filter(subtopic__chapter=self.groups['chemistry']).exclude(pk__in=ids).first()
        invalid=[extra.pk,*ids[1:]];bad_rows=Question.objects.select_related('subtopic__chapter').in_bulk(invalid)
        with self.assertRaises(ValueError):prepare_export(request,{'start_number':1},invalid,bad_rows,[])

    def test_real_download_uses_four_sections_and_forced_marks(self):
        d=self.post('generate',self.config).json()
        with patch('paper_builder.views.build_pdf',return_value=b'%PDF-test') as build:
            r=self.client.post(reverse('download'),{'test_pattern_id':d['plan_id'],'question_ids':json.dumps([q['id'] for q in d['questions']]),'marks':'5','start_number':'1','output_format':'pdf','arrangement':'combined'})
        self.assertEqual(r.status_code,200,r.content)
        details,sections=build.call_args.args[:2]
        self.assertEqual(details['marks'],720);self.assertEqual([label for label,_ in sections],list(LABELS.values()))

    def test_header_summary_pdf_word_and_legacy_export(self):
        from paper_builder.pdf import build_pdf
        from paper_builder.word import build_word
        from docx import Document
        import pdfplumber
        chapter=self.groups['physics'];questions=list(Question.objects.filter(subtopic__chapter=chapter).select_related('subtopic__chapter')[:3])
        request=RequestFactory().post('/download/')
        basic={'title':'Custom test','institution':'OJAS Academy','date':None,'marks':12,'duration':30,'logo':None,'start_number':1,'page_columns':'two','option_layout':'four'}
        details,sections=prepare_export(request,basic,[q.pk for q in questions],{q.pk:q for q in questions},[('Physics',questions)])
        pdf=build_pdf(details,sections,mode='combined')
        with pdfplumber.open(BytesIO(pdf)) as document:
            first=document.pages[0].extract_text();self.assertIn('Chapters covered in this test',first);self.assertIn(chapter.name,first)
            self.assertLess(first.index('Chapters covered'),first.index('PHYSICS'))
        word=Document(BytesIO(build_word(details,sections,'combined')))
        text='\n'.join(p.text for p in word.paragraphs);self.assertIn('Chapters covered in this test',text);self.assertLess(text.index('Chapters covered'),text.index('PHYSICS'))

    def test_write_endpoints_require_csrf(self):
        strict=Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(reverse('test_patterns:generate'),json.dumps(self.config),content_type='application/json').status_code,403)
        self.assertEqual(self.client.get(reverse('test_patterns:generate')).status_code,405)
