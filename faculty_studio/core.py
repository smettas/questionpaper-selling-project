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

def validate(spec,require_scope=True):
    if not isinstance(spec,dict):raise ValueError('Choose a pattern.')
    sections=spec.get('sections',[])
    if not isinstance(sections,list) or not 1<=len(sections)<=8:raise ValueError('Use 1–8 sections.')
    clean=[];total=0;previous_end=0
    for s in sections:
        if not isinstance(s,dict):raise ValueError('Invalid section.')
        subject=s.get('subject');label=str(s.get('label') or '').strip()[:80] or {'physics':'Physics','chemistry':'Chemistry','biology':'Biology','mathematics':'Mathematics'}.get(subject,'');slots=s.get('slots')
        if subject not in Chapter.Subject.values or not label:raise ValueError('Choose a subject and section name.')
        if not isinstance(slots,list) or not 1<=len(slots)<=300 or any(k not in TYPES for k in slots):raise ValueError('Assign a valid type to every position.')
        chapters=s.get('chapters',[]);topics=s.get('topics',[])
        if not isinstance(chapters,list) or not isinstance(topics,list) or any(type(x) is not int or x<=0 for x in chapters+topics):raise ValueError('Invalid syllabus selection.')
        if require_scope and not chapters:raise ValueError(f'{label}: choose the covered chapters before generating questions.')
        if len(chapters)>150 or len(set(chapters))!=len(chapters):raise ValueError('Invalid chapter selection.')
        if Chapter.objects.filter(pk__in=chapters,subject=subject).count()!=len(chapters):raise ValueError('A chapter belongs to another subject.')
        if topics and Subtopic.objects.filter(pk__in=topics,chapter_id__in=chapters).count()!=len(set(topics)):raise ValueError('A topic belongs to another chapter.')
        difficulty=s.get('difficulty','')
        if difficulty not in ('','easy','moderate','hard'):raise ValueError('Invalid difficulty.')
        mode=s.get('format_mode','manual')
        if mode not in ('manual','automatic'):raise ValueError('Choose manual types or automatic mix.')
        raw_start=s.get('start_number');numbering=s.get('numbering','auto' if raw_start in (None,'') else 'explicit')
        if numbering not in ('auto','explicit'):raise ValueError('Invalid numbering mode.')
        start=previous_end+1 if numbering=='auto' else integer(raw_start,1,9999,'Starting question number')
        end=start+len(slots)-1
        if start<=previous_end:raise ValueError(f'{label}: start after question {previous_end} to avoid overlapping numbers.')
        if end>9999:raise ValueError('The last question number must be 9999 or lower.')
        previous_end=end;total+=len(slots)
        clean.append({'label':label,'subject':subject,'chapters':chapters,'topics':list(dict.fromkeys(topics)),'difficulty':difficulty,'slots':slots,'format_mode':mode,'start_number':start,'numbering':numbering})
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
        for i,k in enumerate(s['slots']):jobs.append((offset+i,s,k,s.get('_preferences',[None]*len(s['slots']))[i]))
        offset+=len(s['slots'])
    pools={};ordered=[]
    for pos,s,k,preferred in jobs:
        key=json.dumps([s,k,preferred],sort_keys=True)
        if key not in pools:
            pool=list(scoped(s,k).exclude(pk__in=exclude).values_list('pk',flat=True));rng.shuffle(pool)
            if preferred:
                favourites=set(scoped(s,preferred).values_list('pk',flat=True))
                pool=[pk for pk in pool if pk in favourites]+[pk for pk in pool if pk not in favourites]
            pools[key]=pool
        ordered.append((pos,s,k,key))
    # Bipartite matching prevents overlapping scopes or any-format slots causing false shortages.
    owner={};assigned={}
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


def generate_questions(spec):
    import copy
    prepared=copy.deepcopy(spec)
    # A varied preference order, with all scoped questions as fallback. These are
    # product mix preferences, not a claimed official NEET format quota.
    cycle=['mcq','statement','assertion-reason','mcq','matching','diagram','statement','mcq','graph','mcq']
    for s in prepared['sections']:
        if s.get('format_mode')=='automatic':
            count=len(s['slots']);available=[k for k in TYPES if k!='any' and scoped(s,k).exists()]
            seed=available[:count];rest=[k for k in cycle if k in available] or ['any']
            preferences=seed+[rest[i%len(rest)] for i in range(max(0,count-len(seed)))];rng.shuffle(preferences)
            s['_preferences']=preferences;s['slots']=['any']*count
    chosen=allocate(prepared)
    rows=Question.objects.filter(pk__in=chosen).in_bulk();offset=0
    for s in prepared['sections']:
        if s.get('format_mode')=='automatic':
            s['slots']=[rows[pk].question_visual or rows[pk].question_kind for pk in chosen[offset:offset+len(s['slots'])]]
        offset+=len(s['slots']);s.pop('_preferences',None)
    return prepared,chosen

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
        available=max(0,policy.practice_daily_cap-used)
        profile,_=Profile.objects.get_or_create(user=user)
        new_correct=0
        for pk in correct:
            if not RewardedQuestion.objects.filter(owner=user,question_id=pk).exists():
                RewardedQuestion.objects.create(owner=user,question_id=pk);new_correct+=1
        required=max(1,policy.practice_correct_per_credit)
        # Only capped daily earnings are payable; retain the fractional remainder,
        # not a stockpile of credits that bypasses the next day's limit.
        groups,remainder=divmod(profile.practice_progress+new_correct,required)
        earned=min(groups,available)
        profile.practice_progress=remainder;profile.save(update_fields=['practice_progress'])
        if earned:credit(wallet,user,earned,'Practice reward','practice:'+str(attempt.pk))
        attempt.answers=answers;attempt.score=len(correct);attempt.reward=earned;attempt.submitted=True;attempt.submitted_at=timezone.now();attempt.save()
        return attempt


def award_welcome(user,actor=None):
    from .models import WelcomeClaim
    email=user.email.strip().casefold() or None
    wallet=allowed_wallet(user)
    with transaction.atomic():
        Policy.current();policy=Policy.objects.select_for_update().get(pk=1)
        Wallet.objects.select_for_update().get(pk=wallet.pk)
        if WelcomeClaim.objects.filter(user=user).exists():return False
        if email and WelcomeClaim.objects.filter(email=email).exists():raise ValueError('Welcome credits were already claimed for this email.')
        WelcomeClaim.objects.create(user=user,email=email)
        if policy.welcome_credits:credit(wallet,actor or user,policy.welcome_credits,'Welcome credits','welcome:'+str(user.pk))
        return True


def adjust_wallet(wallet,actor,delta,reason,reference):
    if not actor.is_superuser:raise PermissionError('Only superusers can adjust credits.')
    if type(delta) is not int or not delta or abs(delta)>1000000:raise ValueError('Enter a non-zero adjustment up to 1,000,000 credits.')
    if not reason.strip():raise ValueError('Enter an adjustment reason.')
    with transaction.atomic():
        Wallet.objects.select_for_update().get(pk=wallet.pk)
        old=Ledger.objects.filter(reference=reference).first()
        if old:
            if old.wallet_id!=wallet.pk or old.amount!=delta:raise ValueError('Adjustment reference has already been used.')
            return False
        label=('Admin adjustment: '+reason.strip())[:150]
        if delta>0:credit(wallet,actor,delta,label,reference)
        else:
            debit_locked(wallet,actor,-delta,reference)
            Ledger.objects.filter(reference=reference).update(reason=label)
        return True
