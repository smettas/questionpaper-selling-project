from django.contrib import admin
from .models import TestPlan
@admin.register(TestPlan)
class TestPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "created_at")
    readonly_fields = ("id", "profile", "specification", "created_at")
    def has_add_permission(self, request):
        return False
