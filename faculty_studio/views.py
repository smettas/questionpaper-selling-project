import json,hashlib,uuid
from django.contrib.auth import authenticate,login as session_login,logout as session_logout,get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.core import signing
from django.db import transaction,IntegrityError,DatabaseError
import logging
logger=logging.getLogger(__name__)
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render,redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Policy,Profile,Pattern,Draft,Practice,Paper,Recharge,Ledger
from .core import validate,allocate,generate_questions,scoped,allowed_wallet,balance,reward_attempt,integer,TYPES,award_welcome

def fail(message,status=400):return JsonResponse({'error':str(message)},status=status)

def user_for(request):
    if request.headers.get('Authorization'):
        from native_api.views import auth_user
        return auth_user(request)
    if request.path.startswith('/api/mobile/'):
        raise ValueError('Please sign in.')
    if request.user.is_authenticated and request.user.is_active:return request.user
    raise ValueError('Please sign in.')

def limited(request,label,limit,seconds=3600):
    key='studio-rate:'+hashlib.sha256((label+request.META.get('REMOTE_ADDR','')).encode()).hexdigest()
    n=cache.get(key,0)
    if n>=limit:raise ValueError('Too many requests. Please try again later.')
    cache.set(key,n+1,seconds)

def input_data(request):
    if len(request.body)>150000:raise ValueError('Request too large.')
    try:d=json.loads(request.body or b'{}')
    except (ValueError,UnicodeDecodeError):raise ValueError('Send valid JSON.')
    if not isinstance(d,dict):raise ValueError('Send an object.')
    return d

def account(request,data,register=False):
    if request.method!='POST':return fail('POST required.',405)
    limited(request,'register' if register else 'login',10 if register else 30,900)
    username=data.get('username','');password=data.get('password','')
    if isinstance(username,str):username=username.strip()
    if not isinstance(username,str) or not isinstance(password,str) or not 3<=len(username)<=150 or len(password)>128:raise ValueError('Enter a username (3–150 characters) and password.')
    if register:
        if not Policy.current().registration_open:raise ValueError('Registration is currently closed. Contact the academy.')
        name=data.get('name','');email=data.get('email','');academy=data.get('academy','')
        if isinstance(email,str):email=email.strip()
        if not all(isinstance(v,str) for v in [name,email,academy]) or not 2<=len(name.strip())<=150 or len(academy)>150:raise ValueError('Enter your name and academy (optional).')
        from django.core.validators import validate_email
        from django.contrib.auth.validators import UnicodeUsernameValidator
        UnicodeUsernameValidator()(username)
        email=email.casefold()
        if not email:raise ValueError('Email is required. Use one account per email address.')
        validate_email(email)
        if len(email)>254:raise ValueError('Email is too long.')
        user=get_user_model()(username=username,first_name=name.strip(),email=email)
        validate_password(password,user)
        try:
            with transaction.atomic():
                Policy.current();Policy.objects.select_for_update().get(pk=1)
                from .models import WelcomeClaim
                if get_user_model().objects.filter(email__iexact=email).exists() or WelcomeClaim.objects.filter(email=email).exists():raise ValueError('This email already has an account. Sign in or contact your administrator.')
                user.set_password(password);user.save();Profile.objects.create(user=user,academy=academy.strip());award_welcome(user)
        except IntegrityError:raise ValueError('That username or email is already registered.')
    else:
        user=authenticate(request,username=username,password=password)
        if not user or not user.is_active:return fail('Incorrect username or password.',401)
    # Native requests use bearer tokens; do not create a redundant browser session.
    if not request.path.startswith('/api/mobile/'):
        from django.conf import settings
        session_login(request,user,backend=getattr(user,'backend',settings.AUTHENTICATION_BACKENDS[0]))
    from native_api.views import AUTH_SALT,MAX_AGE
    token=signing.dumps({'uid':user.pk,'auth':user.get_session_auth_hash()},salt=AUTH_SALT)
    return JsonResponse({'name':user.get_full_name() or user.username,'account_id':user.pk,'token':token,'expires_in':MAX_AGE})

@never_cache
def home(request):
    if not request.user.is_authenticated:return render(request,'faculty_studio/login.html')
    return render(request,'faculty_studio/home.html')

@require_POST
def logout(request):
    session_logout(request);return redirect('/studio/')

def meta(q):
    return {'id':q.pk,'subject':q.subtopic.chapter.get_subject_display(),'chapter':q.subtopic.chapter.name,'subtopic':q.subtopic.name,'kind':q.question_kind,'visual':q.question_visual,'difficulty':q.difficulty}

def draft_json(d):
    rows=__import__('question_bank.models',fromlist=['Question']).Question.objects.filter(pk__in=d.question_ids).select_related('subtopic__chapter').in_bulk()
    return {'id':str(d.pk),'name':d.name,'spec':d.spec,'question_ids':d.question_ids,'questions':[meta(rows[pk]) for pk in d.question_ids if pk in rows]}

@never_cache
def api(request,action):
    try:
        data=input_data(request) if request.method=='POST' else {}
        if action in ('login','register'):return account(request,data,action=='register')
        try:request.user=user_for(request)
        except ValueError as exc:return fail(exc,401)
        methods={'dashboard':'GET','patterns':'GET','pattern-save':'POST','pattern-delete':'POST','generate':'POST','draft':'GET','replace':'POST','preview':'POST','practice-start':'POST','practice-view':'GET','practice-submit':'POST','paper-files':'GET','recharge':'POST','catalog':'GET','usage-report':'GET','availability':'POST','preview-batch':'POST'}
        if action not in methods:return fail('Unknown action.',404)
        if methods[action]!=request.method:return fail('Method not allowed.',405)
        user=request.user
        if action=='catalog':
            from test_patterns.views import catalog
            return catalog(request)
        if action=='usage-report':
            import csv,io,base64
            wallet=allowed_wallet(user,request.GET.get('wallet','personal'))
            output=io.StringIO();writer=csv.writer(output)
            writer.writerow(['Date','User','Credits','Reason','Reference'])
            for entry in Ledger.objects.filter(wallet=wallet).select_related('actor').order_by('pk').iterator():
                def safe(v):
                    value=str(v)
                    return "'"+value if value.startswith(('=','+','-','@')) else value
                writer.writerow([entry.created_at.isoformat(),safe(entry.actor.get_username()),entry.amount,safe(entry.reason),safe(entry.reference)])
            return JsonResponse({'files':[{'name':'Wallet usage.csv','type':'text/csv','data':base64.b64encode(('\ufeff'+output.getvalue()).encode()).decode()}]})
        if action=='dashboard':
            p=Policy.current();personal=allowed_wallet(user);wallets=[{'id':'personal','label':'Personal wallet','balance':balance(personal)}]
            profile=Profile.objects.filter(user=user).select_related('institution').first()
            if profile and profile.institution:
                w=allowed_wallet(user,profile.institution_id);wallets.append({'id':str(profile.institution_id),'label':profile.institution.name,'balance':balance(w)})
            return JsonResponse({'name':user.get_full_name() or user.username,'wallets':wallets,'price':p.credits_per_question,'paise_per_credit':p.paise_per_credit,'practice_per_correct':0,'practice_correct_per_credit':p.practice_correct_per_credit,'practice_progress':Profile.objects.get_or_create(user=user)[0].practice_progress,'welcome_credits':p.welcome_credits,'practice_daily_cap':p.practice_daily_cap,'valid_days':p.credit_valid_days,'low_balance':p.low_balance,'staff_free':bool(user.is_staff and p.staff_free),'papers':list(Paper.objects.filter(owner=user).order_by('-pk').values('id','title','count','charged','created_at')[:30]),'ledger':list(Ledger.objects.filter(wallet=personal).order_by('-pk').values('amount','reason','created_at')[:40]),'recharges':list(Recharge.objects.filter(user=user).order_by('-pk').values('id','rupees','credits','status','created_at')[:20]),'practice':list(Practice.objects.filter(owner=user,submitted=True).order_by('-submitted_at').values('id','score','reward','submitted_at')[:20])})
        if action=='patterns':return JsonResponse({'patterns':list(Pattern.objects.filter(owner=user).order_by('-updated_at').values('id','name','spec'))})
        if action=='pattern-save':
            spec=validate(data.get('spec'),require_scope=False);name=str(data.get('name','')).strip()
            if not 1<=len(name)<=120:raise ValueError('Name your pattern (1–120 characters).')
            obj=Pattern.objects.filter(pk=data.get('id'),owner=user).first() if data.get('id') else None
            if data.get('id') and not obj:return fail('Pattern not found.',404)
            if obj:obj.name=name;obj.spec=spec;obj.save()
            else:
                if Pattern.objects.filter(owner=user).count()>=100:raise ValueError('Keep at most 100 saved patterns.')
                obj=Pattern.objects.create(owner=user,name=name,spec=spec)
            return JsonResponse({'id':obj.pk,'name':obj.name,'spec':obj.spec})
        if action=='pattern-delete':
            Pattern.objects.filter(pk=data.get('id'),owner=user).delete();return JsonResponse({'ok':True})
        if action=='availability':
            spec=validate(data.get('spec'));result=[]
            from collections import Counter
            for s in spec['sections']:
                requested=Counter(['any']*len(s['slots']) if s.get('format_mode')=='automatic' else s['slots'])
                result.append({'label':s['label'],'types':[{'type':k,'label':label,'available':scoped(s,k).count(),'requested':requested[k]} for k,label in TYPES.items()]})
            return JsonResponse({'sections':result})
        if action=='generate':
            limited(request,'generate:'+str(user.pk),60)
            spec=validate(data.get('spec'));spec,chosen=generate_questions(spec)
            obj=Draft.objects.create(owner=user,name=str(data.get('name','Custom pattern'))[:120],spec=spec,question_ids=chosen)
            return JsonResponse(draft_json(obj))
        if action=='draft':
            obj=Draft.objects.filter(pk=request.GET.get('id'),owner=user).first()
            return JsonResponse(draft_json(obj)) if obj else fail('Draft not found.',404)
        if action=='replace':
            with transaction.atomic():
                d=Draft.objects.select_for_update().filter(pk=data.get('draft_id'),owner=user).first()
                if not d:return fail('Draft not found.',404)
                pos=integer(data.get('position'),0,len(d.question_ids)-1,'Position');i=pos
                for s in d.spec['sections']:
                    if i<len(s['slots']):break
                    i-=len(s['slots'])
                available=list(scoped(s,s['slots'][i]).exclude(pk__in=d.question_ids).values_list('pk',flat=True))
                if not available:raise ValueError('No unused question matches this exact position. The existing question is unchanged.')
                from random import SystemRandom
                ids=d.question_ids.copy();ids[pos]=SystemRandom().choice(available);d.question_ids=ids;d.save(update_fields=['question_ids'])
            return JsonResponse(draft_json(d))
        if action=='preview-batch':
            from native_api.views import serialize
            from question_bank.models import Question
            wanted=data.get('ids',[])
            if not isinstance(wanted,list) or not 1<=len(wanted)<=12 or any(type(pk) is not int or pk<1 for pk in wanted):raise ValueError('Request 1–12 question previews.')
            rows=Question.objects.filter(pk__in=wanted,active=True).select_related('subtopic__chapter').in_bulk();questions=[];failed=[]
            for pk in dict.fromkeys(wanted):
                if pk not in rows:failed.append({'id':pk,'error':'Question is no longer available.'});continue
                try:questions.append(serialize(rows[pk]))
                except (ValueError,TypeError,KeyError,RuntimeError):failed.append({'id':pk,'error':'Preview could not load. Retry or replace this question.'})
            return JsonResponse({'questions':questions,'failed':failed})
        if action=='preview':
            from native_api.views import serialize
            from question_bank.models import Question
            pk=integer(data.get('id'),1,2**63-1,'Question')
            row=Question.objects.filter(pk=pk,active=True).select_related('subtopic__chapter').first()
            if not row:return fail('Question not found.',404)
            return JsonResponse({'question':serialize(row)})
        if action=='practice-start':
            limited(request,'practice:'+str(user.pk),30)
            spec=validate(data.get('spec'))
            if spec['total']>100:raise ValueError('Practice supports up to 100 questions.')
            spec,chosen=generate_questions(spec)
            from question_bank.models import Question
            keys={str(q.pk):q.correct_option for q in Question.objects.filter(pk__in=chosen)}
            obj=Practice.objects.create(owner=user,question_ids=chosen,answer_key=keys)
            return JsonResponse({'id':str(obj.pk),'count':len(chosen)})
        if action=='practice-view':
            from native_api.views import serialize
            from question_bank.models import Question
            obj=Practice.objects.filter(pk=request.GET.get('id'),owner=user).first()
            if not obj:return fail('Test not found.',404)
            pos=int(request.GET.get('position','0'));integer(pos,0,len(obj.question_ids)-1,'Position')
            q=Question.objects.filter(pk=obj.question_ids[pos]).select_related('subtopic__chapter').first()
            if not q:return fail('Question unavailable.',404)
            payload=serialize(q)
            if not obj.submitted:
                payload.pop('answer',None);payload.pop('hint_blocks',None);payload['diagrams']=[d for d in payload['diagrams'] if d['placement']=='question']
            else:payload['answer']=obj.answer_key[str(q.pk)]
            return JsonResponse({'question':payload,'count':len(obj.question_ids),'submitted':obj.submitted,'score':obj.score,'reward':obj.reward})
        if action=='practice-submit':
            obj=reward_attempt(user,data.get('id'),data.get('answers'))
            return JsonResponse({'score':obj.score,'total':len(obj.question_ids),'reward':obj.reward,'submitted':True})
        if action=='paper-files':
            obj=Paper.objects.filter(pk=request.GET.get('id'),owner=user).first()
            from .exporting import load_files
            return JsonResponse({'files':load_files(obj),'charged':0}) if obj else fail('Paper not found.',404)
        if action=='recharge':
            limited(request,'recharge:'+str(user.pk),10)
            wallet=allowed_wallet(user,data.get('wallet','personal'));rupees=integer(data.get('rupees'),1,100000,'Recharge rupees');ref=str(data.get('reference','')).strip()
            if not 5<=len(ref)<=100:raise ValueError('Enter a payment or request reference (5–100 characters).')
            p=Policy.current()
            if p.paise_per_credit<1:raise ValueError('Ask admin to configure the credit price.')
            credits=rupees*100//p.paise_per_credit
            obj,created=Recharge.objects.get_or_create(user=user,reference=ref,defaults={'wallet':wallet,'rupees':rupees,'credits':credits})
            return JsonResponse({'id':obj.pk,'status':obj.status,'message':'Request recorded. Credits are added only after admin verifies and approves payment.'})
    except (ValueError,TypeError,KeyError,ValidationError,Practice.DoesNotExist) as exc:return fail('; '.join(exc.messages) if isinstance(exc,ValidationError) else exc)

# OJAS_REGISTRATION_DIAGNOSTICS
_original_api=api
@never_cache
def api(request,action):
    try:
        return _original_api(request,action)
    except DatabaseError:
        logger.exception('Faculty studio database failure; action=%s',action)
        return JsonResponse({'error':'The account service database is not ready. Ask the administrator to run migrations and studio_healthcheck.','code':'STUDIO_DATABASE_NOT_READY'},status=503)
    except Exception:
        reference=uuid.uuid4().hex[:10]
        logger.exception('Faculty studio server error; reference=%s action=%s',reference,action)
        return JsonResponse({'error':'The account service could not finish this request. If you already submitted registration, try signing in before registering again. Support reference: '+reference,'code':'STUDIO_SERVER_ERROR','reference':reference},status=500)
