import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from question_bank.models import Question
from question_bank.audit_rules import VERSION, inspect_record, plain

# Protect spreadsheet users from formulas in bank text.
def cell(value):
    value = str(value if value is not None else '')
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value

class Command(BaseCommand):
    help = 'Read-only bank diagnostics; NOT a complete scientific answer verification.'
    def add_arguments(self,p):
        p.add_argument('--out',default='audit_reports')
        p.add_argument('--subject', choices=['physics','chemistry','biology','mathematics'])
        p.add_argument('--chapter-id',type=int)
        p.add_argument('--after-id',type=int,default=0)
        p.add_argument('--limit',type=int)
        p.add_argument('--include-unpublished',action='store_true')
        p.add_argument('--base-url',default='https://questionpaper-selling-project-production.up.railway.app')
    def handle(self,*args,**o):
        if o['limit'] is not None and o['limit'] <= 0:
            raise CommandError('--limit must be positive')
        out=Path(o['out']); out.mkdir(parents=True,exist_ok=False)
        q=Question.objects.filter(pk__gt=o['after_id']).order_by('pk')
        if not o['include_unpublished']: q=q.filter(active=True)
        if o['subject']: q=q.filter(subtopic__chapter__subject=o['subject'])
        else: q=q.filter(subtopic__chapter__subject__in=['physics','chemistry'])
        if o['chapter_id']: q=q.filter(subtopic__chapter_id=o['chapter_id'])
        q=q.values('pk','correct_option','structured','difficulty','subtopic__name','subtopic__chapter__name','subtopic__chapter__subject')
        if o['limit']: q=q[:o['limit']]
        counts=Counter(); seen={}; scanned=flagged=last=0
        fields=['question_id','severity','rule','reason','subject','chapter','topic','difficulty','stored_key','stem','option_1','option_2','option_3','option_4','hint','admin_url']
        with (out/'suspected_errors.csv').open('w',newline='',encoding='utf-8-sig') as f, (out/'coverage.csv').open('w',newline='',encoding='utf-8-sig') as g:
            writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader()
            coverage=csv.writer(g); coverage.writerow(['question_id','diagnostic_findings','scientific_answer_status'])
            for r in q.iterator(chunk_size=500):
                scanned+=1; last=r['pk']; c=r['structured']; findings=inspect_record(c,r['correct_option'])
                c=c if isinstance(c,dict) else {}
                opts=c.get('options',[]); opts=opts if isinstance(opts,list) else []
                if plain(c.get('stem')) and len(opts)==4:
                    # Diagram questions require pixel comparison; text-only signature is insufficient.
                    if not c.get('diagrams'):
                        sig=hashlib.sha256(json.dumps([plain(c.get('stem')).casefold(),sorted(plain(x).casefold() for x in opts)],ensure_ascii=False).encode()).hexdigest()
                        if sig in seen: findings.append(('POSSIBLE_DUPLICATE','review',f'Same normalized stem and option set as Bank #{seen[sig]}; check context.'))
                        else: seen[sig]=last
                if findings: flagged+=1
                coverage.writerow([last,len(findings),'NOT_INDEPENDENTLY_VERIFIED'])
                for code,severity,reason in findings:
                    counts[code]+=1
                    row=dict(question_id=last,severity=severity,rule=code,reason=reason,subject=r['subtopic__chapter__subject'],chapter=r['subtopic__chapter__name'],topic=r['subtopic__name'],difficulty=r['difficulty'],stored_key=r['correct_option'],stem=c.get('stem',''),hint=c.get('hint',''),admin_url=f"{o['base_url'].rstrip('/')}/admin/question_bank/question/{last}/change/")
                    row.update({f'option_{i+1}':opts[i] if i<len(opts) else '' for i in range(4)})
                    writer.writerow({k:cell(v) for k,v in row.items()})
                if scanned%5000==0: self.stdout.write(f'Scanned {scanned}; flagged records {flagged}; last ID {last}',ending='\n')
        summary=dict(version=VERSION,scanned=scanned,flagged_records=flagged,findings=dict(counts),last_id=last,scientifically_verified=0,database_writes=0,warning='Diagnostic scan only. Unflagged does not mean scientifically correct. No general Physics/Chemistry independent solver is included.',filters={k:o[k] for k in ('subject','chapter_id','after_id','limit','include_unpublished')})
        (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        self.stdout.write(json.dumps(summary,indent=2)); self.stdout.write(f'Reports: {out.resolve()}')
