from django.contrib import admin,messages
from django.db import transaction
from django.utils import timezone
from .models import Policy,Institution,Profile,Wallet,Grant,Ledger,Recharge,Pattern,Draft,Paper,Practice,RewardedQuestion
from .core import credit

@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    exclude=('practice_per_correct',)
    def has_add_permission(self,request):return not Policy.objects.exists() and request.user.is_superuser
    def has_delete_permission(self,request,obj=None):return False
    def has_change_permission(self,request,obj=None):return request.user.is_superuser

@admin.register(Recharge)
class RechargeAdmin(admin.ModelAdmin):
    list_display=('id','user','wallet','rupees','credits','reference','status','created_at')
    list_filter=('status',);search_fields=('reference','user__username')
    readonly_fields=('user','wallet','rupees','credits','reference','status','created_at','reviewed_by','reviewed_at')
    actions=['approve','reject']
    def has_add_permission(self,r):return False
    def has_delete_permission(self,r,obj=None):return False
    @admin.action(description='Approve verified payments and add credits',permissions=['change'])
    def approve(self,request,queryset):
        if not request.user.is_superuser:self.message_user(request,'Only superusers approve credits.',messages.ERROR);return
        for pk in queryset.values_list('pk',flat=True):
            with transaction.atomic():
                obj=Recharge.objects.select_for_update().get(pk=pk)
                if obj.status!='pending':continue
                if Recharge.objects.filter(status='approved',reference=obj.reference).exclude(pk=pk).exists():
                    self.message_user(request,f'Reference already approved: {obj.reference}',messages.ERROR);continue
                credit(obj.wallet,request.user,obj.credits,'Verified recharge','recharge:'+str(obj.pk))
                obj.status='approved';obj.reviewed_by=request.user;obj.reviewed_at=timezone.now();obj.save()
        self.message_user(request,'Pending verified requests processed. Approval is idempotent.')
    @admin.action(description='Reject pending recharge requests',permissions=['change'])
    def reject(self,request,queryset):
        if request.user.is_superuser:queryset.filter(status='pending').update(status='rejected',reviewed_by=request.user,reviewed_at=timezone.now())

@admin.register(Grant,Ledger,Paper,Practice,RewardedQuestion)
class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self,r):return False
    def has_delete_permission(self,r,obj=None):return False
    def has_change_permission(self,r,obj=None):return False
    def get_readonly_fields(self,r,obj=None):return [f.name for f in self.model._meta.fields]

@admin.register(Institution,Profile)
class MembershipAdmin(admin.ModelAdmin):
    def has_module_permission(self,r):return r.user.is_superuser
    def has_view_permission(self,r,obj=None):return r.user.is_superuser
    def has_change_permission(self,r,obj=None):return r.user.is_superuser
    def has_add_permission(self,r):return r.user.is_superuser
    def has_delete_permission(self,r,obj=None):return r.user.is_superuser

from .models import Promotion
@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display=('wallet','credits','reason','created_by','created_at')
    readonly_fields=('created_by','created_at')
    def has_view_permission(self,r,obj=None):return r.user.is_superuser
    def has_add_permission(self,r):return r.user.is_superuser
    def has_change_permission(self,r,obj=None):return r.user.is_superuser and obj is None
    def has_delete_permission(self,r,obj=None):return False
    def save_model(self,request,obj,form,change):
        if change or not request.user.is_superuser:raise ValueError('Promotions are append-only and require a superuser.')
        if not obj.credits:raise ValueError('Choose a positive number of credits.')
        with transaction.atomic():
            obj.created_by=request.user;obj.save();credit(obj.wallet,request.user,obj.credits,'Promotion: '+obj.reason,'promotion:'+str(obj.pk))


from django import forms
from django.urls import path,reverse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.core.exceptions import PermissionDenied
from .core import balance,adjust_wallet,award_welcome
import uuid
class AdjustmentForm(forms.Form):
    amount=forms.IntegerField(label='Credits to add or deduct',min_value=-1000000,max_value=1000000,help_text='Positive adds credits; negative deducts credits. Balance cannot go below zero.')
    reason=forms.CharField(max_length=130,widget=forms.Textarea(attrs={'rows':2}))
    reference=forms.UUIDField(widget=forms.HiddenInput)

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    change_form_template='admin/faculty_studio/wallet/change_form.html'
    list_display=('id','user','institution','available_credits')
    search_fields=('user__username','user__email','institution__name')
    readonly_fields=('user','institution','available_credits')
    def available_credits(self,obj):return balance(obj)
    def has_add_permission(self,r):return False
    def has_delete_permission(self,r,obj=None):return False
    def has_change_permission(self,r,obj=None):return r.user.is_superuser
    def get_urls(self):return [path('<int:object_id>/adjust/',self.admin_site.admin_view(self.adjust),name='faculty_studio_wallet_adjust')]+super().get_urls()
    def adjust(self,request,object_id):
        if not request.user.is_superuser:raise PermissionDenied
        obj=self.get_object(request,str(object_id))
        if obj is None:raise PermissionDenied
        form=AdjustmentForm(request.POST or None,initial={'reference':uuid.uuid4()})
        if request.method=='POST' and form.is_valid():
            try:
                changed=adjust_wallet(obj,request.user,form.cleaned_data['amount'],form.cleaned_data['reason'],'admin-adjust:'+str(form.cleaned_data['reference']))
                self.message_user(request,'Credits adjusted.' if changed else 'This adjustment was already applied.')
                return redirect('admin:faculty_studio_wallet_change',obj.pk)
            except ValueError as exc:form.add_error(None,str(exc))
        context={**self.admin_site.each_context(request),'opts':self.model._meta,'original':obj,'title':'Adjust credits: '+str(obj),'form':form,'balance':balance(obj)}
        return TemplateResponse(request,'admin/faculty_studio/wallet/adjust.html',context)
    def change_view(self,request,object_id,form_url='',extra_context=None):
        return super().change_view(request,object_id,form_url,extra_context={**(extra_context or {}),'can_adjust':request.user.is_superuser,'adjust_url':reverse('admin:faculty_studio_wallet_adjust',args=[object_id])})
