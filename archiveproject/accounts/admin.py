from django.contrib import admin
from .models import ActivityLog, SystemUser

admin.site.register(SystemUser)


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
