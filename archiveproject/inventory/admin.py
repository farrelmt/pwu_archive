from django.contrib import admin

from .models import CompanyMember, InventoryAccess, InventoryActivity, InventoryItem


@admin.register(CompanyMember)
class CompanyMemberAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "full_name", "division", "position", "status")
    list_filter = ("division", "status")
    search_fields = ("employee_id", "full_name", "email", "position")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("asset_code", "item_name", "category", "quantity", "condition", "status", "assigned_to")
    list_filter = ("category", "condition", "status")
    search_fields = ("asset_code", "item_name", "serial_number", "brand", "model")


admin.site.register(InventoryAccess)
admin.site.register(InventoryActivity)
