import functools,hashlib,json,base64
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from pathlib import PurePosixPath
from django.db import transaction
from django.http import JsonResponse
from question_bank.models import Question
from .models import Paper,Wallet,Draft,Policy
from .core import allowed_wallet,balance,debit_locked,scoped

def load_files(paper):
    result=[]
    for item in paper.files:
        if 'data' in item:result.append(item);continue
        with default_storage.open(item['path'],'rb') as f:blob=f.read()
        result.append({'name':item['name'],'type':item['type'],'data':base64.b64encode(blob).decode()})
    return result

def prepare_sections(request,details,ids,rows,selected):
    value=request.POST.get('studio_draft_id')
    if not value:return details,selected
    draft=Draft.objects.filter(pk=value,owner=request.user).first()
    if not draft or ids!=draft.question_ids:raise ValueError('This selection no longer matches your saved pattern draft. Reload it.')
    offset=0;sections=[]
    for s in draft.spec['sections']:
        subset=ids[offset:offset+len(s['slots'])];offset+=len(subset)
        for pk,kind in zip(subset,s['slots']):
            if not scoped(s,kind).filter(pk=pk).exists():raise ValueError('A slot no longer matches the saved pattern. Replace it before generating.')
        sections.append((s['label'],[rows[pk] for pk in subset]))
    return details,sections

def meter_export(view):
    @functools.wraps(view)
    def wrapped(request,*a,**kw):
        if not getattr(request,'user',None) or not request.user.is_authenticated:return JsonResponse({'error':'Please sign in.'},status=401)
        try:
            ids=json.loads(request.POST.get('question_ids','[]'))
            if not isinstance(ids,list) or not 1<=len(ids)<=300 or any(type(x) is not int or x<=0 for x in ids) or len(set(ids))!=len(ids):raise ValueError('Select 1–300 distinct questions.')
            wallet=allowed_wallet(request.user,request.POST.get('studio_wallet','personal'))
            data={k:request.POST.getlist(k) for k in sorted(request.POST) if k not in ('csrfmiddlewaretoken','plan_ticket','studio_wallet')}
            # Bind cache to bank content as well as layout, order, wallet and uploaded logo.
            bank=list(Question.objects.filter(pk__in=ids,active=True).order_by('pk').values('pk','structured','correct_option','artwork','hint'))
            if len(bank)!=len(ids):raise ValueError('A question is no longer available.')
            logo=request.FILES.get('logo');blob=b''
            if logo:
                blob=logo.read(2_000_001);logo.seek(0)
                if len(blob)>2_000_000:raise ValueError('Logo must be under 2 MB.')
            fingerprint=hashlib.sha256(json.dumps([data,bank,wallet.pk,hashlib.sha256(blob).hexdigest()],sort_keys=True,default=str).encode()).hexdigest()
            previous=Paper.objects.filter(owner=request.user,fingerprint=fingerprint).first()
            if previous:return JsonResponse({'files':load_files(previous),'paper_id':previous.pk,'charged':0,'original_charge':previous.charged,'reused':True})
            policy=Policy.current();cost=0 if request.user.is_staff and policy.staff_free else len(ids)*policy.credits_per_question
            if cost and request.POST.get('studio_expected_cost')!=str(cost):raise ValueError('Review the current credit cost and confirm generation again.')
            if balance(wallet)<cost:raise ValueError(f'This paper needs {cost} credits. Available: {balance(wallet)}. Recharge before generating.')
            # No deduction for validation/render failures. Render before entering the wallet lock.
            response=view(request,*a,**kw)
            if response.status_code!=200:return response
            payload=json.loads(response.content)
            if not payload.get('files'):raise ValueError('No files were generated. No credits deducted.')
            with transaction.atomic():
                Wallet.objects.select_for_update().get(pk=wallet.pk)
                previous=Paper.objects.filter(owner=request.user,fingerprint=fingerprint).first()
                if previous:return JsonResponse({'files':load_files(previous),'paper_id':previous.pk,'charged':0,'reused':True})
                obj=Paper.objects.create(owner=request.user,wallet=wallet,fingerprint=fingerprint,title=request.POST.get('title','Question paper')[:150] or 'Question paper',count=len(ids),charged=cost,files=[])
                paths=[];stored=[]
                try:
                    for i,item in enumerate(payload['files']):
                        suffix=PurePosixPath(item['name']).suffix
                        if suffix not in ('.pdf','.docx'):raise ValueError('Unexpected generated file type.')
                        path=default_storage.save(f'faculty-papers/{request.user.pk}/{obj.pk}/{i}{suffix}',ContentFile(base64.b64decode(item['data'],validate=True)))
                        paths.append(path);stored.append({'name':item['name'],'type':item['type'],'path':path})
                    obj.files=stored;obj.save(update_fields=['files'])
                    if cost:debit_locked(wallet,request.user,cost,'paper:'+str(obj.pk))
                except Exception:
                    for path in paths:
                        try:default_storage.delete(path)
                        except Exception:pass
                    raise
            payload.update(paper_id=obj.pk,charged=cost,reused=False,balance=balance(wallet))
            return JsonResponse(payload)
        except (ValueError,TypeError,KeyError,OSError) as exc:return JsonResponse({'error':str(exc)},status=400)
    return wrapped
