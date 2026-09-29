from django.contrib import admin

from .models import CompanyMember, InventoryAccess, InventoryActivity, InventoryItem, InventoryReport


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


@admin.register(InventoryReport)
class InventoryReportAdmin(admin.ModelAdmin):
    list_display = ("item", "reporter", "report_type", "status", "created_at")
    list_filter = ("report_type", "status")
    search_fields = ("item__asset_code", "item__item_name", "reporter__username", "description")
