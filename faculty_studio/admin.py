from django.contrib import admin,messages
from django.db import transaction
from django.utils import timezone
from .models import Policy,Institution,Profile,Wallet,Grant,Ledger,Recharge,Pattern,Draft,Paper,Practice,RewardedQuestion
from .core import credit

@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
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

@admin.register(Grant,Ledger,Paper,Practice,RewardedQuestion,Wallet)
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
