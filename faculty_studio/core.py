import hashlib,json
from datetime import timedelta
from random import SystemRandom
from django.db import transaction
from django.db.models import Sum,Q
from django.utils import timezone
from question_bank.models import Question,Chapter,Subtopic
from .models import Policy,Wallet,Grant,Ledger,Profile,Pattern,Draft,Practice,RewardedQuestion

TYPES={'any':'Any format','mcq':'Standard MCQ','assertion-reason':'Assertion–reason','statement':'Statement','matching':'Matching','diagram':'Diagram','graph':'Graph'}
rng=SystemRandom()

def integer(x,low,high,label):
    if type(x) is not int or not low<=x<=high:raise ValueError(f'{label} must be {low}–{high}.')
    return x

def validate(spec):
    if not isinstance(spec,dict):raise ValueError('Choose a pattern.')
    sections=spec.get('sections',[])
    if not isinstance(sections,list) or not 1<=len(sections)<=8:raise ValueError('Use 1–8 sections.')
    clean=[];total=0
    for s in sections:
        if not isinstance(s,dict):raise ValueError('Invalid section.')
        subject=s.get('subject');label=str(s.get('label','')).strip()[:80];slots=s.get('slots')
        if subject not in Chapter.Subject.values or not label:raise ValueError('Choose a subject and section name.')
        if not isinstance(slots,list) or not 1<=len(slots)<=300 or any(k not in TYPES for k in slots):raise ValueError('Assign a valid type to every position.')
        chapters=s.get('chapters',[]);topics=s.get('topics',[])
        if not isinstance(chapters,list) or not isinstance(topics,list) or any(type(x) is not int or x<=0 for x in chapters+topics):raise ValueError('Invalid syllabus selection.')
        if not chapters or len(chapters)>150 or len(set(chapters))!=len(chapters):raise ValueError('Select chapters for every section.')
        if Chapter.objects.filter(pk__in=chapters,subject=subject).count()!=len(chapters):raise ValueError('A chapter belongs to another subject.')
        if topics and Subtopic.objects.filter(pk__in=topics,chapter_id__in=chapters).count()!=len(set(topics)):raise ValueError('A topic belongs to another chapter.')
        difficulty=s.get('difficulty','')
        if difficulty not in ('','easy','moderate','hard'):raise ValueError('Invalid difficulty.')
        total+=len(slots)
        clean.append({'label':label,'subject':subject,'chapters':chapters,'topics':list(dict.fromkeys(topics)),'difficulty':difficulty,'slots':slots})
    if total>300:raise ValueError('A paper can contain at most 300 questions.')
    return {'sections':clean,'total':total}

def scoped(section,kind='any'):
    q=Question.objects.filter(active=True,subtopic__chapter_id__in=section['chapters'],subtopic__chapter__subject=section['subject'])
    if section['topics']:q=q.filter(subtopic_id__in=section['topics'])
    if section['difficulty']:q=q.filter(difficulty=section['difficulty'])
    if kind in ('diagram','graph'):q=q.filter(question_visual=kind)
    elif kind!='any':
        q=q.filter(question_kind=kind)
        if kind=='mcq':q=q.exclude(question_visual__in=['diagram','graph'])
    return q

def allocate(spec,exclude=()):
    # Constrained slots first: 'any' can never consume a question needed by a rare format.
    jobs=[];offset=0
    for s in spec['sections']:
        for i,k in enumerate(s['slots']):jobs.append((offset+i,s,k))
        offset+=len(s['slots'])
    pools={};ordered=[]
    for pos,s,k in jobs:
        key=json.dumps([s,k],sort_keys=True)
        if key not in pools:pools[key]=list(scoped(s,k).exclude(pk__in=exclude).values_list('pk',flat=True))
        ordered.append((pos,s,k,key))
    # Bipartite matching prevents overlapping scopes or any-format slots causing false shortages.
    owner={};assigned={}
    for pool in pools.values():rng.shuffle(pool)
    def place(job,visited):
        for pk in pools[job[3]]:
            if pk in visited:continue
            visited.add(pk)
            if pk not in owner or place(owner[pk],visited):
                owner[pk]=job;assigned[job[0]]=pk;return True
        return False
    for job in sorted(ordered,key=lambda j:len(pools[j[3]])):
        if not place(job,set()):raise ValueError(f"Not enough distinct {TYPES[job[2]]} questions for {job[1]['label']}. Change its scope or slot types.")
    return [assigned[i] for i in range(spec['total'])]

def allowed_wallet(user,which='personal'):
    if which in ('personal','',None):return Wallet.objects.get_or_create(user=user)[0]
    profile=Profile.objects.filter(user=user,institution_id=which).first()
    if profile is None:raise ValueError('You are not a member of this institutional wallet.')
    return Wallet.objects.get_or_create(institution_id=profile.institution_id)[0]

def balance(wallet):
    return Grant.objects.filter(wallet=wallet,expires_at__gt=timezone.now()).aggregate(n=Sum('remaining'))['n'] or 0

def credit(wallet,actor,amount,reason,reference):
    with transaction.atomic():
        Wallet.objects.select_for_update().get(pk=wallet.pk)
        old=Ledger.objects.filter(reference=reference).first()
        if old:return old
        days=Policy.current().credit_valid_days
        Grant.objects.create(wallet=wallet,amount=amount,remaining=amount,reason=reason,reference=reference,expires_at=timezone.now()+timedelta(days=days))
        return Ledger.objects.create(wallet=wallet,actor=actor,amount=amount,reason=reason,reference=reference)

def debit_locked(wallet,actor,amount,reference):
    if balance(wallet)<amount:raise ValueError(f'Insufficient credits. This paper needs {amount}; available {balance(wallet)}.')
    left=amount
    for g in Grant.objects.select_for_update().filter(wallet=wallet,remaining__gt=0,expires_at__gt=timezone.now()).order_by('expires_at','pk'):
        used=min(left,g.remaining);g.remaining-=used;g.save(update_fields=['remaining']);left-=used
        if not left:break
    Ledger.objects.create(wallet=wallet,actor=actor,amount=-amount,reason='Question paper generated',reference=reference)

def reward_attempt(user,attempt_id,answers):
    if not isinstance(answers,dict):raise ValueError('Submit answer choices.')
    wallet=allowed_wallet(user)
    with transaction.atomic():
        Wallet.objects.select_for_update().get(pk=wallet.pk)
        attempt=Practice.objects.select_for_update().get(pk=attempt_id,owner=user)
        if attempt.submitted:return attempt
        if set(answers)-set(map(str,attempt.question_ids)):raise ValueError('Answer does not belong to this test.')
        if any(type(v) is not int or v not in range(0,5) for v in answers.values()):raise ValueError('Choose options 1–4, or skip.')
        correct=[pk for pk in attempt.question_ids if answers.get(str(pk))==attempt.answer_key[str(pk)]]
        policy=Policy.current();today=timezone.localdate()
        used=Practice.objects.filter(owner=user,submitted_at__date=today).aggregate(n=Sum('reward'))['n'] or 0
        available=max(0,policy.practice_daily_cap-used);earned=0
        for pk in correct:
            first=not RewardedQuestion.objects.filter(owner=user,question_id=pk).exists()
            if first:RewardedQuestion.objects.create(owner=user,question_id=pk)
            if first:earned+=min(policy.practice_per_correct,max(0,available-earned))
        if earned:credit(wallet,user,earned,'Practice reward','practice:'+str(attempt.pk))
        attempt.answers=answers;attempt.score=len(correct);attempt.reward=earned;attempt.submitted=True;attempt.submitted_at=timezone.now();attempt.save()
        return attempt
