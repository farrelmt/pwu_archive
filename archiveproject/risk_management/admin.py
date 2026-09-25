from django.contrib import admin

from .models import RiskAccess, RiskActivity, RiskDivision, RiskRegister


@admin.register(RiskDivision)
class RiskDivisionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")


@admin.register(RiskAccess)
class RiskAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "division", "is_active")
    list_filter = ("role", "is_active")


@admin.register(RiskRegister)
class RiskRegisterAdmin(admin.ModelAdmin):
    list_display = ("risk_code", "title", "division", "category", "status", "updated_at")
    list_filter = ("division", "category", "status")
    search_fields = ("risk_code", "title", "description", "risk_owner")


admin.site.register(RiskActivity)
