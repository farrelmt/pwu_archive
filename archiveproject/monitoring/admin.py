from django.contrib import admin

from .models import Assignment


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "month", "division", "responsible", "due_date", "status")
    list_filter = ("month", "division", "status")
    search_fields = ("title", "description", "responsible__username")
