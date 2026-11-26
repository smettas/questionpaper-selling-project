from uuid import UUID
from django.utils.html import escape
from .core import LABELS, SECTIONS, PROFILES, JEE_COUNTS, JEE_SECTIONS, subject_for
from .models import TestPlan


def prepare_pattern_export(request, details, ids, rows):
    try:
        plan = TestPlan.objects.get(pk=UUID(request.POST['test_pattern_id']))
    except (ValueError, KeyError, TestPlan.DoesNotExist) as exc:
        raise ValueError("This test plan is unavailable. Generate the test again.") from exc
    spec = plan.specification
    exam = request.POST.get('exam')
    is_jee = spec['profile'] in (*JEE_COUNTS, 'jeecumulative', 'jeecustom')
    if (exam == 'jee' and not is_jee) or (exam == 'neet' and is_jee):
        raise ValueError('This test plan belongs to a different examination.')
    if len(ids) != spec['total']:
        raise ValueError(f"This pattern requires exactly {spec['total']} questions. Replace removed questions or generate a new test.")
    grouped = {section: [] for section in spec['targets']}
    for pk in ids:
        row = rows[pk]
        matches = [section for section, scope in spec['sections'].items()
                   if row.subtopic.chapter.subject == subject_for(section)
                   and row.subtopic.chapter_id in scope['chapters'] and row.subtopic_id in scope['topics']]
        if len(matches) != 1:
            raise ValueError(f"Question #{pk} is outside this test's covered syllabus or Biology split.")
        grouped[matches[0]].append(row)
    for section, target in spec['targets'].items():
        if len(grouped[section]) != target:
            raise ValueError(f"{LABELS[section]} requires {target} questions; {len(grouped[section])} are selected.")
    if spec['profile'] in ('grand', 'cumulative') and details.get('start_number') != 1:
        raise ValueError("Grand and Cumulative tests start at question 1.")
    ordered = [section for section in JEE_SECTIONS if section in grouped] if is_jee else list(spec["targets"])
    sections = [(LABELS[section], grouped[section]) for section in ordered]
    details = {**details, 'marks': spec['marks'], 'title': details.get('title') or PROFILES[spec['profile']]}
    coverage = []
    from question_bank.chapter_order import order_chapters
    for label, questions in sections:
        chapters = {q.subtopic.chapter_id: {'id':q.subtopic.chapter_id, 'name':q.subtopic.chapter.name,
                    'level':q.subtopic.chapter.level, 'subject':q.subtopic.chapter.subject} for q in questions}
        names = [f"{c['name']} (Class {c['level']})" for c in order_chapters(list(chapters.values()))]
        coverage.append(f"{label}: " + '; '.join(names))
    details['covered_chapters'] = coverage
    details['test_summary'] = f"{spec['total']} questions | " + ' | '.join(f"{LABELS[k]} {spec['targets'][k]}" for k in ordered)
    return details, sections


def pdf_coverage(details, width):
    if not details.get('covered_chapters'):
        return []
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    style = ParagraphStyle('CoveredChapters',fontName='Helvetica',fontSize=8,leading=11,spaceAfter=3)
    result = []
    if details.get('test_summary'):
        result.append(Paragraph(str(escape(details['test_summary'])),style))
    result.append(Paragraph('<b>Chapters covered in this test</b>',style))
    result.extend(Paragraph(str(escape(line)),style) for line in details['covered_chapters'])
    result.append(Spacer(1,8))
    return result


def word_coverage(doc, details):
    if not details.get('covered_chapters'):
        return
    from docx.shared import Pt
    if details.get('test_summary'):
        doc.add_paragraph(details['test_summary'])
    p=doc.add_paragraph();p.add_run('Chapters covered in this test').bold=True
    p.paragraph_format.space_after=Pt(3)
    for line in details['covered_chapters']:
        p=doc.add_paragraph(line);p.paragraph_format.space_after=Pt(3)
        for run in p.runs:
            run.font.size=Pt(8)


def prepare_export(request, details, ids, rows, existing_sections):
    exam = request.POST.get('exam')
    allowed = {'jee': {'physics', 'chemistry', 'mathematics'}, 'neet': {'physics', 'chemistry', 'biology'}}
    if exam:
        if exam not in allowed:
            raise ValueError('Unknown examination.')
        if any(row.subtopic.chapter.subject not in allowed[exam] for row in rows.values()):
            raise ValueError('Selected questions contain a subject outside this examination.')
    if request.POST.get('test_pattern_id'):
        return prepare_pattern_export(request, details, ids, rows)
    # Ordinary/manual papers receive the same actual-chapter summary too.
    coverage = []
    from question_bank.chapter_order import order_chapters
    for label, questions in existing_sections:
        chapters = {q.subtopic.chapter_id: {'id': q.subtopic.chapter_id, 'name': q.subtopic.chapter.name,
                    'level': q.subtopic.chapter.level, 'subject': q.subtopic.chapter.subject} for q in questions}
        names = [f"{c['name']} (Class {c['level']})" for c in order_chapters(list(chapters.values()))]
        coverage.append(f"{label}: " + '; '.join(names))
    return {**details, 'covered_chapters': coverage}, existing_sections
