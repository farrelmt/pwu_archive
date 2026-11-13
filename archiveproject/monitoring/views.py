from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.directory import MEMBER_DIVISION_ORDER

from .access import can_edit_assignment, monitor_required
from .forms import AssignmentForm
from .models import Assignment, current_month


def selected_month(value):
    if not value:
        return current_month()
    try:
        return date.fromisoformat(f"{value}-01")
    except ValueError:
        raise Http404("Bulan tidak valid")


def board_url(month, division=""):
    params = {"month": month.strftime("%Y-%m")}
    if division:
        params["division"] = division
    return f"{reverse('monitoring:board')}?{urlencode(params)}"


@monitor_required
@require_GET
def board(request):
    month = selected_month(request.GET.get("month"))
    division = request.GET.get("division", "")
    if division and division not in MEMBER_DIVISION_ORDER:
        raise Http404("Divisi tidak valid")
    assignments = Assignment.objects.filter(month=month).select_related("responsible", "created_by")
    if division:
        assignments = assignments.filter(division=division)
    columns = [
        {"status": key, "label": label, "items": []}
        for key, label in Assignment.STATUS_CHOICES
    ]
    by_status = {column["status"]: column for column in columns}
    for assignment in assignments:
        assignment.editable = can_edit_assignment(request.user, assignment)
        by_status[assignment.status]["items"].append(assignment)
    previous_month = (month - timedelta(days=1)).replace(day=1)
    next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    return render(request, "monitoring/board.html", {
        "columns": columns,
        "month": month,
        "division": division,
        "divisions": MEMBER_DIVISION_ORDER,
        "previous_url": board_url(previous_month, division),
        "next_url": board_url(next_month, division),
        "total_count": sum(len(column["items"]) for column in columns),
        "done_count": len(by_status["done"]["items"]),
    })


@monitor_required
@require_http_methods(["GET", "POST"])
def assignment_create(request):
    month = selected_month(request.GET.get("month"))
    division = request.GET.get("division", "")
    initial = {"month": month, "start_date": timezone.localdate(), "division": division,
               "responsible": request.user}
    form = AssignmentForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        assignment.created_by = request.user
        assignment.save()
        messages.success(request, "Tugas berhasil dibuat.")
        return redirect(board_url(assignment.month, assignment.division))
    return render(request, "monitoring/assignment_form.html", {
        "form": form, "is_create": True, "back_url": board_url(month, division),
    })


@monitor_required
@require_GET
def assignment_detail(request, pk):
    assignment = get_object_or_404(Assignment.objects.select_related("responsible", "created_by"), pk=pk)
    return render(request, "monitoring/assignment_detail.html", {
        "assignment": assignment,
        "can_edit": can_edit_assignment(request.user, assignment),
        "back_url": board_url(assignment.month, assignment.division),
    })


@monitor_required
@require_http_methods(["GET", "POST"])
def assignment_edit(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    if not can_edit_assignment(request.user, assignment):
        raise PermissionDenied
    form = AssignmentForm(request.POST or None, instance=assignment)
    if request.method == "POST" and form.is_valid():
        assignment = form.save()
        messages.success(request, "Tugas berhasil diperbarui.")
        return redirect("monitoring:assignment_detail", pk=assignment.pk)
    return render(request, "monitoring/assignment_form.html", {
        "form": form, "assignment": assignment, "is_create": False,
        "back_url": reverse("monitoring:assignment_detail", args=[assignment.pk]),
    })


@monitor_required
@require_POST
def assignment_status(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    if not can_edit_assignment(request.user, assignment):
        raise PermissionDenied
    status = request.POST.get("status")
    if status not in dict(Assignment.STATUS_CHOICES):
        raise Http404("Status tidak valid")
    if assignment.status != status:
        assignment.status = status
        assignment.save(update_fields=["status", "updated_at"])
    return redirect(board_url(assignment.month, assignment.division))
