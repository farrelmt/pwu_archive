from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import SystemUser


@admin.register(SystemUser)
class SystemUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("PWU permissions", {"fields": ("role", "phone")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("PWU permissions", {"fields": ("role", "phone")}),
    )
    list_display = UserAdmin.list_display + ("role", "is_active")
    list_filter = UserAdmin.list_filter + ("role",)
