from datetime import date, timedelta
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.directory import MEMBER_DIVISION_ORDER

from .access import can_edit_assignment, monitor_required
from .forms import AssignmentForm, ChecklistGroupForm, ChecklistItemEditForm, ChecklistStepsForm
from .models import Assignment, ChecklistGroup, ChecklistItem, current_month


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


def visible_in_month(month):
    return Q(month=month) | (
        Q(month__lt=month) & (
            Q(status__in=["todo", "doing"]) | Q(completed_at__date__gte=month)
        )
    )


def return_url(request, assignment, *, default_detail=False):
    value = request.POST.get("return_month")
    if value:
        month = selected_month(value)
        division = request.POST.get("return_division", "")
        if division and division not in MEMBER_DIVISION_ORDER:
            raise Http404("Divisi tidak valid")
        return board_url(month, division)
    if default_detail:
        return reverse("monitoring:assignment_detail", args=[assignment.public_id])
    return board_url(assignment.month, assignment.division)


def detail_edit_url(assignment, anchor="edit-tugas"):
    return f"{reverse('monitoring:assignment_detail', args=[assignment.public_id])}?edit=1#{anchor}"


@monitor_required
@require_GET
def board(request):
    month = selected_month(request.GET.get("month"))
    division = request.GET.get("division", "")
    if division and division not in MEMBER_DIVISION_ORDER:
        raise Http404("Divisi tidak valid")
    assignments = Assignment.objects.filter(visible_in_month(month)).select_related(
        "responsible", "created_by"
    ).prefetch_related("checklist_groups__items").annotate(
        checklist_total=Count("checklist_items"),
        checklist_done=Count("checklist_items", filter=Q(checklist_items__is_done=True)),
    )
    if division:
        assignments = assignments.filter(division=division)
    columns = [
        {"status": key, "label": label, "items": []}
        for key, label in Assignment.STATUS_CHOICES
    ]
    by_status = {column["status"]: column for column in columns}
    for assignment in assignments:
        assignment.editable = can_edit_assignment(request.user, assignment)
        assignment.is_carried = assignment.month < month
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
@require_GET
def assignment_list(request):
    search = request.GET.get("q", "").strip()
    division = request.GET.get("division", "")
    status = request.GET.get("status", "")
    month_value = request.GET.get("month", "")
    if division and division not in MEMBER_DIVISION_ORDER:
        raise Http404("Divisi tidak valid")
    if status and status not in dict(Assignment.STATUS_CHOICES):
        raise Http404("Status tidak valid")
    month = selected_month(month_value) if month_value else None
    assignments = Assignment.objects.select_related("responsible").annotate(
        checklist_total=Count("checklist_items"),
        checklist_done=Count("checklist_items", filter=Q(checklist_items__is_done=True)),
    )
    if search:
        assignments = assignments.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
            | Q(responsible__username__icontains=search)
            | Q(responsible__first_name__icontains=search)
            | Q(responsible__last_name__icontains=search)
        )
    if division:
        assignments = assignments.filter(division=division)
    if status:
        assignments = assignments.filter(status=status)
    if month:
        assignments = assignments.filter(visible_in_month(month))
    page = Paginator(assignments.order_by("-month", "due_date", "pk"), 25).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "monitoring/assignment_list.html", {
        "page": page, "search": search, "division": division, "status": status,
        "month_value": month_value, "divisions": MEMBER_DIVISION_ORDER,
        "statuses": Assignment.STATUS_CHOICES, "filter_query": query.urlencode(),
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
        ChecklistGroup.objects.create(assignment=assignment, title="Tugas")
        messages.success(request, "Tugas berhasil dibuat.")
        return redirect(board_url(assignment.month, assignment.division))
    return render(request, "monitoring/assignment_form.html", {
        "form": form, "is_create": True, "back_url": board_url(month, division),
    })


@monitor_required
@require_http_methods(["GET", "POST"])
def assignment_detail(request, public_id):
    assignment = get_object_or_404(Assignment.objects.select_related("responsible", "created_by").prefetch_related("checklist_groups__items"), public_id=public_id)
    form = AssignmentForm(request.POST or None, instance=assignment)
    editor_open = request.GET.get("edit") == "1" or request.method == "POST"
    if editor_open:
        form.fields["title"].widget = forms.Textarea(attrs={"rows": 2})
        for field in form.fields.values():
            field.widget.attrs["form"] = "assignment-edit-form"
    if request.method == "POST":
        if not can_edit_assignment(request.user, assignment):
            raise PermissionDenied
        if form.is_valid():
            form.save()
            messages.success(request, "Tugas berhasil diperbarui.")
            return redirect(detail_edit_url(assignment))
    checklist_groups = list(assignment.checklist_groups.all())
    checklist_items = [item for group in checklist_groups for item in group.items.all()]
    for group in checklist_groups:
        items = list(group.items.all())
        group.item_count = len(items)
        group.done_count = sum(item.is_done for item in items)
        group.progress_percent = round(group.done_count * 100 / group.item_count) if group.item_count else 0
    checklist_done = sum(item.is_done for item in checklist_items)
    return render(request, "monitoring/assignment_detail.html", {
        "assignment": assignment,
        "form": form,
        "editor_open": editor_open,
        "can_edit": can_edit_assignment(request.user, assignment),
        "back_url": board_url(assignment.month, assignment.division),
        "checklist_items": checklist_items,
        "checklist_groups": checklist_groups,
        "checklist_done": checklist_done,
        "checklist_progress": round(checklist_done * 100 / len(checklist_items)) if checklist_items else 0,
    })


@monitor_required
@require_http_methods(["GET", "POST"])
def assignment_edit(request, public_id):
    assignment = get_object_or_404(
        Assignment.objects.prefetch_related("checklist_groups__items"), public_id=public_id,
    )
    if not can_edit_assignment(request.user, assignment):
        raise PermissionDenied
    if request.method == "POST":
        form = AssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            form.save()
            messages.success(request, "Tugas berhasil diperbarui.")
        else:
            messages.error(request, "Periksa kembali rincian tugas.")
    return redirect(detail_edit_url(assignment))


@monitor_required
@require_POST
def assignment_delete(request, public_id):
    assignment = get_object_or_404(Assignment, public_id=public_id)
    if not can_edit_assignment(request.user, assignment):
        raise PermissionDenied
    destination = board_url(assignment.month, assignment.division)
    assignment.delete()
    messages.success(request, "Tugas berhasil dihapus.")
    return redirect(destination)


@monitor_required
@require_POST
def assignment_status(request, public_id):
    assignment = get_object_or_404(Assignment, public_id=public_id)
    if not can_edit_assignment(request.user, assignment):
        raise PermissionDenied
    status = request.POST.get("status")
    if status not in dict(Assignment.STATUS_CHOICES):
        raise Http404("Status tidak valid")
    if assignment.status != status:
        assignment.status = status
        assignment.save(update_fields=["status", "updated_at"])
    return redirect(return_url(request, assignment))


@monitor_required
@require_POST
def checklist_group_add(request, public_id):
    assignment = get_object_or_404(Assignment, public_id=public_id)
    if not can_edit_assignment(request.user, assignment):
        raise PermissionDenied
    if "title" not in request.POST and "steps" not in request.POST:
        with transaction.atomic():
            locked_assignment = Assignment.objects.select_for_update().get(pk=assignment.pk)
            names = set(locked_assignment.checklist_groups.values_list("title", flat=True))
            number = len(names) + 1
            while f"Checklist {number}" in names:
                number += 1
            group = ChecklistGroup.objects.create(assignment=locked_assignment, title=f"Checklist {number}")
            ChecklistItem.objects.create(assignment=locked_assignment, group=group, text="Task 1")
        return redirect(detail_edit_url(assignment, f"checklist-group-{group.pk}"))
    group_form = ChecklistGroupForm(request.POST)
    steps_form = ChecklistStepsForm(request.POST)
    if group_form.is_valid() and steps_form.is_valid():
        with transaction.atomic():
            group = group_form.save(commit=False)
            group.assignment = assignment
            group.save()
            ChecklistItem.objects.bulk_create([
                ChecklistItem(assignment=assignment, group=group, text=step)
                for step in steps_form.cleaned_data["steps"]
            ])
    else:
        messages.error(request, "Isi nama checklist dan minimal satu tugas (maksimal 20 tugas, 220 karakter per tugas).")
    return redirect(detail_edit_url(assignment))


@monitor_required
@require_POST
def checklist_group_edit(request, public_id, group_pk):
    assignment = get_object_or_404(Assignment, public_id=public_id)
    if not can_edit_assignment(request.user, assignment):
        raise PermissionDenied
    group = get_object_or_404(ChecklistGroup, pk=group_pk, assignment=assignment)
    form = ChecklistGroupForm(request.POST, instance=group)
    if form.is_valid():
        form.save()
    else:
        messages.error(request, "Judul checklist wajib diisi (maksimal 120 karakter).")
    return redirect(detail_edit_url(assignment))


@monitor_required
@require_POST
def checklist_group_delete(request, public_id, group_pk):
    assignment = get_object_or_404(Assignment, public_id=public_id)
    if not can_edit_assignment(request.user, assignment):
        raise PermissionDenied
    group = get_object_or_404(ChecklistGroup, pk=group_pk, assignment=assignment)
    group.delete()
    return redirect(detail_edit_url(assignment))


@monitor_required
@require_POST
def checklist_add(request, public_id, group_pk):
    assignment = get_object_or_404(Assignment, public_id=public_id)
    if not can_edit_assignment(request.user, assignment):
        raise PermissionDenied
    group = get_object_or_404(ChecklistGroup, pk=group_pk, assignment=assignment)
    form = ChecklistStepsForm(request.POST)
    if form.is_valid():
        ChecklistItem.objects.bulk_create([
            ChecklistItem(assignment=assignment, group=group, text=step)
            for step in form.cleaned_data["steps"]
        ])
    else:
        messages.error(request, "Periksa tugas checklist: satu per baris, maksimal 220 karakter per tugas.")
    return redirect(detail_edit_url(assignment))


@monitor_required
@require_POST
def checklist_toggle(request, public_id, item_pk):
    assignment = get_object_or_404(Assignment, public_id=public_id)
    if not can_edit_assignment(request.user, assignment):
        raise PermissionDenied
    item = get_object_or_404(ChecklistItem, pk=item_pk, assignment=assignment)
    item.is_done = not item.is_done
    item.save(update_fields=["is_done"])
    return redirect("monitoring:assignment_detail", public_id=public_id)


@monitor_required
@require_POST
def checklist_edit(request, public_id, item_pk):
    assignment = get_object_or_404(Assignment, public_id=public_id)
    if not can_edit_assignment(request.user, assignment):
        raise PermissionDenied
    item = get_object_or_404(ChecklistItem, pk=item_pk, assignment=assignment)
    form = ChecklistItemEditForm(request.POST, instance=item)
    if form.is_valid():
        form.save()
    else:
        messages.error(request, "Tugas checklist tidak boleh kosong dan maksimal 220 karakter.")
    return redirect(detail_edit_url(assignment))


@monitor_required
@require_POST
def checklist_delete(request, public_id, item_pk):
    assignment = get_object_or_404(Assignment, public_id=public_id)
    if not can_edit_assignment(request.user, assignment):
        raise PermissionDenied
    item = get_object_or_404(ChecklistItem, pk=item_pk, assignment=assignment)
    item.delete()
    return redirect(detail_edit_url(assignment))
