"""Authenticated adapters for the native app. Existing website views remain unchanged."""
import base64
import copy
from datetime import timedelta
from functools import lru_cache
import hashlib
from io import BytesIO
import json
import re
from django.contrib.auth import authenticate, get_user_model
from django.core import signing
from django.core.cache import cache
from django.http import JsonResponse, QueryDict
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from PIL import Image
from question_bank.models import Question
from syllabus_builder import views as syllabus
from test_patterns import views as patterns
from paper_builder import views as paper
from paper_builder.structured import MATH, SCRIPT, normalize_math, render_equation, split_question_label

AUTH_SALT='ojas.native.auth.v1'
PLAN_SALT='ojas.native.plan.v1'
MAX_AGE=7*24*3600

def fail(message,status=400):return JsonResponse({'error':message},status=status)

def body(request):
    return syllabus.json_body(request)

def auth_user(request):
    header=request.headers.get('Authorization','')
    if not header.startswith('Bearer ') or len(header)>4096:raise ValueError('Please sign in again.')
    try:
        data=signing.loads(header[7:],salt=AUTH_SALT,max_age=MAX_AGE)
        user=get_user_model().objects.get(pk=data['uid'],is_active=True)
        if not constant_time_compare(data.get('auth',''),user.get_session_auth_hash()):raise ValueError()
        return user
    except (signing.BadSignature,KeyError,TypeError,ValueError,get_user_model().DoesNotExist):
        raise ValueError('Your session expired. Please sign in again.')

@csrf_exempt
@never_cache
def login(request):
    if request.method!='POST':return fail('POST required.',405)
    try:
        data=body(request);username=data.get('username');password=data.get('password')
        if not isinstance(username,str) or not isinstance(password,str) or not 1<=len(username)<=150 or len(password)>1024:raise ValueError('Enter your username and password.')
        bucket='native-login:'+hashlib.sha256((request.META.get('REMOTE_ADDR','')+':'+username.casefold()).encode()).hexdigest()
        attempts=cache.get(bucket,0)
        if attempts>=15:return fail('Too many sign-in attempts. Wait 15 minutes.',429)
        cache.set(bucket,attempts+1,900)
        user=authenticate(request,username=username,password=password)
        if not user or not user.is_active:return fail('Invalid username or password.',401)
        cache.delete(bucket)
        token=signing.dumps({'uid':user.pk,'auth':user.get_session_auth_hash()},salt=AUTH_SALT)
        return JsonResponse({'token':token,'expires_in':MAX_AGE,'name':user.get_full_name() or user.get_username(),'account_id':user.pk})
    except ValueError as exc:return fail(str(exc))

@lru_cache(maxsize=512)
def math_image(expression):
    blob=render_equation(expression,'png',dpi=216)
    with Image.open(BytesIO(blob)) as im:width,height=im.size
    return {'type':'math','uri':'data:image/png;base64,'+base64.b64encode(blob).decode(),'width':width/3,'height':height/3,'alt':expression}

def tokens(text):
    output=[]
    for part in MATH.split(normalize_math(str(text or ''))):
        if MATH.fullmatch(part):output.append(math_image(part[2:-2]));continue
        for chunk in SCRIPT.split(part):
            match=re.fullmatch(r'<(sub|sup)>(.*?)</\1>',chunk,re.S)
            if match:output.append({'type':match[1],'value':match[2]})
            elif chunk:output.append({'type':'text','value':chunk})
    return output

def blocks(text):
    # Existing matching convention is one row per line, separated by '|'.
    result=[];table=[]
    def flush():
        if table:result.append({'type':'table','rows':table.copy()});table.clear()
    for line in str(text or '').splitlines():
        protected=[m.span() for m in MATH.finditer(line)]
        divider=next((i for i,ch in enumerate(line) if ch=='|' and not any(start<=i<end for start,end in protected)),None)
        if divider is not None:
            cells=[line[:divider],line[divider+1:]];table.append([tokens(c.strip()) for c in cells])
        else:
            flush()
            if line.strip():
                label,remainder=split_question_label(line)
                result.append({'type':'paragraph','tokens':([{'type':'strong','value':label}] if label else [])+tokens(remainder if label else line)})
    flush();return result

def serialize(row):
    c=row.structured if isinstance(row.structured,dict) else {}
    result={'id':row.pk,'subject':row.subtopic.chapter.get_subject_display(),'chapter':row.subtopic.chapter.name,'chapter_id':row.subtopic.chapter_id,'topic_id':row.subtopic_id,'subtopic':row.subtopic.name,'difficulty':row.difficulty,'kind':row.question_kind,'visual':row.question_visual,'answer':row.correct_option,'level':row.subtopic.chapter.level,'stem_blocks':blocks(c.get('stem','')),'options':[tokens(o) for o in c.get('options',[])],'hint_blocks':blocks(c.get('hint','')),'diagrams':[]}
    for d in c.get('diagrams',[]):
        if isinstance(d,dict) and isinstance(d.get('png'),str):
            try:
                binary=base64.b64decode(d['png'],validate=True)
                with Image.open(BytesIO(binary)) as im:w,h=im.size
                result['diagrams'].append({'placement':d.get('placement','question'),'uri':'data:image/png;base64,'+d['png'],'ratio':w/max(1,h)})
            except (ValueError,OSError):raise ValueError('A diagram could not be decoded.')
    if not c:
        for placement,asset in [('question',row.artwork),('hint',row.hint)]:
            if not asset:continue
            with asset.open('rb') as f:binary=f.read(4_000_001)
            if len(binary)>4_000_000:raise ValueError('Image too large for mobile preview.')
            with Image.open(BytesIO(binary)) as im:
                w,h=im.size;image=im.convert('RGB');buf=BytesIO();image.save(buf,'PNG')
            result['diagrams'].append({'placement':placement,'uri':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode(),'ratio':w/max(1,h)})
    result['image_only']=not bool(c)
    return result

def delegate(request,view,data=None):
    r=copy.copy(request)
    if data is not None:
        r._body=json.dumps(data).encode();r._read_started=False
    response=view(r)
    if response.status_code>=400 and 'application/json' not in response.get('Content-Type',''):
        return fail(response.content.decode('utf-8',errors='replace')[:2000],response.status_code)
    return response

def ticket(request,value):
    try:
        data=signing.loads(value,salt=PLAN_SALT,max_age=MAX_AGE)
        if data['uid']!=request.user.pk:raise ValueError()
        return data['plan']
    except (signing.BadSignature,KeyError,TypeError,ValueError):raise ValueError('This test belongs to another or expired session. Generate it again.')

@csrf_exempt
@never_cache
def endpoint(request,action):
    # OJAS_FACULTY_API
    if action.startswith('studio-'):
        from faculty_studio.views import api
        return api(request, action[7:])
    try:request.user=auth_user(request)
    except ValueError as exc:return fail(str(exc),401)
    methods={'catalog':'GET','browse':'GET','counts':'GET','sample':'POST','details':'POST','generate':'POST','replace':'POST','report':'POST','export':'POST','me':'GET'}
    if action not in methods:return fail('Unknown endpoint.',404)
    if request.method!=methods[action]:return fail('Method not allowed.',405)
    try:
        if action=='me':return JsonResponse({'name':request.user.get_full_name() or request.user.get_username(),'account_id':request.user.pk})
        if action=='catalog':return delegate(request,patterns.catalog)
        if action=='counts':return delegate(request,syllabus.counts)
        if action=='browse':
            from django.core.paginator import Paginator
            data={key:request.GET.get(key,'') for key in ('subject','difficulty','question_type')}
            data['chapters']=request.GET.getlist('chapters');data['topics']=request.GET.getlist('topics')
            query=syllabus.query_for(data).select_related('subtopic__chapter').order_by('pk')
            page=Paginator(query,12).get_page(request.GET.get('page',1))
            questions=[]
            for row in page:
                questions.append({'id':row.pk,'subject':row.subtopic.chapter.get_subject_display(),'chapter':row.subtopic.chapter.name,'chapter_id':row.subtopic.chapter_id,'topic_id':row.subtopic_id,'subtopic':row.subtopic.name,'difficulty':row.difficulty,'kind':row.question_kind,'visual':row.question_visual,'level':row.subtopic.chapter.level})
            return JsonResponse({'questions':questions,'page':page.number,'pages':page.paginator.num_pages,'count':page.paginator.count})
        if action=='sample':return delegate(request,syllabus.sample)
        if action=='details':
            wanted=syllabus.ids(body(request).get('ids',[]),'question',12)
            if not wanted:raise ValueError('Choose questions to preview.')
            rows=Question.objects.filter(active=True,pk__in=wanted).select_related('subtopic__chapter').in_bulk();result=[];failed=[]
            for pk in wanted:
                if pk not in rows:failed.append({'id':pk,'error':'Question is no longer published.'});continue
                try:result.append(serialize(rows[pk]))
                except (ValueError,KeyError,TypeError,RuntimeError) as exc:failed.append({'id':pk,'error':'Preview failed; report the question.'})
            return JsonResponse({'questions':result,'failed':failed})
        if action=='generate':
            response=delegate(request,patterns.generate)
            if response.status_code==200:
                data=json.loads(response.content);data['plan_ticket']=signing.dumps({'uid':request.user.pk,'plan':data['plan_id']},salt=PLAN_SALT);return JsonResponse(data)
            return response
        if action=='replace':
            data=body(request);data['plan_id']=ticket(request,data.pop('plan_ticket',''))
            # Existing replace returns SVG previews, which the native client does not use.
            response=delegate(request,patterns.replace,data)
            if response.status_code==200:
                data=json.loads(response.content);q=data['question'];q.pop('preview',None);return JsonResponse(data)
            return response
        if action=='export':
            # Trigger multipart parsing before replacing POST. Django validates logo and selections.
            post=request.POST.copy();request.FILES
            if post.get('plan_ticket'):post['test_pattern_id']=ticket(request,post.pop('plan_ticket')[0])
            elif post.get('test_pattern_id'):raise ValueError('Use a native test ticket.')
            r=copy.copy(request);r.POST=post
            return delegate(r,paper.download)
        if action=='report':
            data=body(request);pk=syllabus.number(data.get('question_id'),'Question ID',1,2**63-1)
            from syllabus_builder.models import CorrectionReport
            if data.get('category') not in dict(CorrectionReport._meta.get_field('category').choices):raise ValueError('Choose a correction category.')
            note=data.get('note','')
            if not isinstance(note,str) or not 10<=len(note.strip())<=2000:raise ValueError('Describe the problem in 10–2000 characters.')
            recent=CorrectionReport.objects.filter(reporter=request.user,created_at__gte=timezone.now()-timedelta(hours=1))
            if recent.count()>=20:return fail('Report limit reached. Try later.',429)
            if recent.filter(question_id=pk,category=data['category'],note=note.strip()).exists():return JsonResponse({'message':'This correction was already recorded.'})
            row=Question.objects.filter(pk=pk,active=True).first()
            if row is None:return fail('Question is unavailable.',404)
            c=row.structured or {};snap={k:c.get(k,'') for k in ('stem','options','hint')};snap['answer']=row.correct_option
            obj=CorrectionReport.objects.create(question=row,category=data['category'],note=note.strip(),snapshot=snap,reporter=request.user,session_key=salted_hmac('ojas.native.reports',str(request.user.pk)).hexdigest())
            return JsonResponse({'id':obj.pk,'message':'Correction sent for staff review. Question unchanged.'},status=201)
    except (ValueError,TypeError,KeyError) as exc:return fail(str(exc))
