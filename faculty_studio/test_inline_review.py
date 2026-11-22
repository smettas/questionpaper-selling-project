from django.test import TestCase,RequestFactory
from faculty_studio import tests as previous_tests
from faculty_studio.core import validate,generate_questions
from faculty_studio.models import Draft
from faculty_studio.exporting import prepare_sections

class InlineReviewTests(TestCase):
    setUp=previous_tests.StudioTests.setUp
    spec=previous_tests.StudioTests.spec
    post=previous_tests.StudioTests.post
    def test_numbering_roundtrip_and_overlap(self):
        s=self.spec();s['sections'][0].update(start_number=46,numbering='explicit')
        clean=validate(s);self.assertEqual(clean['sections'][0]['start_number'],46)
        other={**s['sections'][0],'numbering':'auto'};s['sections'].append(other)
        self.assertEqual(validate(s)['sections'][1]['start_number'],54)
        s['sections'][1].update(numbering='explicit',start_number=50)
        with self.assertRaises(ValueError):validate(s)
    def test_auto_mix_fallback_and_manual_sequence(self):
        s=self.spec(['any']*17);s['sections'][0]['format_mode']='automatic'
        clean,ids=generate_questions(validate(s));self.assertEqual(len(set(ids)),17)
        self.assertEqual(set(clean['sections'][0]['slots']),{'mcq','assertion-reason','statement','matching'})
        manual=self.spec(['matching','statement','assertion-reason','mcq'])
        clean,ids=generate_questions(validate(manual))
        from question_bank.models import Question
        self.assertEqual([Question.objects.get(pk=p).question_kind for p in ids],manual['sections'][0]['slots'])
    def test_full_preview_batch_and_inactive(self):
        self.q[1].active=False;self.q[1].save()
        r=self.post('preview-batch',{'ids':[self.q[0].pk,self.q[1].pk]}).json()
        self.assertEqual(len(r['questions']),1);self.assertIn('options',r['questions'][0]);self.assertEqual(r['failed'][0]['id'],self.q[1].pk)
        self.assertEqual(self.post('preview-batch',{'ids':list(range(1,14))}).status_code,400)
        self.client.logout();self.assertEqual(self.post('preview-batch',{'ids':[self.q[0].pk]}).status_code,401)
    def test_export_starts_and_coverage(self):
        s=self.spec(['mcq']*2);s['sections'][0].update(start_number=46,numbering='explicit');spec=validate(s);ids=[q.pk for q in self.q[:2]]
        draft=Draft.objects.create(owner=self.user,name='Numbered paper',spec=spec,question_ids=ids)
        request=RequestFactory().post('/',{'studio_draft_id':str(draft.pk)});request.user=self.user
        details,sections=prepare_sections(request,{'start_number':1},ids,{q.pk:q for q in self.q},[])
        self.assertEqual(details['section_starts'],[46]);self.assertIn('Q46–47',details['covered_chapters'][0])
