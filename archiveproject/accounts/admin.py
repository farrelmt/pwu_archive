from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import ActivityLog, SystemUser


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


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'actor_username',
        'category',
        'action',
        'target_label',
        'success',
    )
    list_filter = ('category', 'action', 'success', 'created_at')
    search_fields = (
        'actor_username',
        'description',
        'target_label',
        'ip_address',
    )
    readonly_fields = [
        field.name for field in ActivityLog._meta.fields
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
