from decimal import Decimal
from uuid import uuid4

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .access import inventory_required, inventory_write_required
from .forms import CompanyMemberForm, InventoryItemForm, InventoryReportForm, PersonalInventoryItemForm, NewInventoryReportForm, category_section
from .models import CompanyMember, InventoryActivity, InventoryItem, InventoryReport


@inventory_required
def dashboard(request):
    if not request.can_edit_inventory:
        try:
            member = request.user.company_member_profile
        except ObjectDoesNotExist:
            return render(request, "inventory/my_inventory_missing.html")
        return redirect("inventory:member_detail", pk=member.pk)
    items = InventoryItem.objects.select_related("assigned_to")
    total_value = sum((item.total_value for item in items), Decimal("0"))
    return render(request, "inventory/dashboard.html", {
        "member_count": CompanyMember.objects.filter(status="active").count(),
        "item_count": sum(item.quantity for item in items),
        "assigned_count": items.filter(status="assigned").count(),
        "maintenance_count": items.filter(status="maintenance").count(),
        "total_value": total_value,
        "recent_items": items.order_by("-created_at")[:8],
    })


@inventory_write_required
def member_list(request):
    members = CompanyMember.objects.all()
    search = request.GET.get("q", "").strip()
    division = request.GET.get("division", "").strip()
    status = request.GET.get("status", "").strip()
    if search:
        members = members.filter(Q(employee_id__icontains=search) | Q(full_name__icontains=search) | Q(position__icontains=search))
    if division:
        members = members.filter(division=division)
    if status in dict(CompanyMember.STATUS_CHOICES):
        members = members.filter(status=status)
    divisions = CompanyMember.objects.order_by("division").values_list("division", flat=True).distinct()
    return render(request, "inventory/member_list.html", {
        "page_obj": Paginator(members, 20).get_page(request.GET.get("page")),
        "divisions": divisions, "statuses": CompanyMember.STATUS_CHOICES,
        "filters": {"q": search, "division": division, "status": status},
    })


@inventory_required
def member_detail(request, pk):
    member = get_object_or_404(CompanyMember, pk=pk)
    if not request.can_edit_inventory and member.user_id != request.user.pk:
        raise PermissionDenied("Anda hanya dapat melihat inventaris milik sendiri.")
    assigned_items = member.inventory_items.all().order_by("category", "item_name", "asset_code")
    hardware_items = assigned_items.filter(
        category__in={"computer", "laptop", "peripheral", "component", "network", "hardware"}
    )
    software_items = assigned_items.filter(category="software")
    other_items = assigned_items.exclude(
        category__in={"computer", "laptop", "peripheral", "component", "network", "hardware", "software"}
    )
    return render(request, "inventory/member_detail.html", {
        "member": member,
        "hardware_items": hardware_items,
        "software_items": software_items,
        "other_items": other_items,
    })


@inventory_required
def my_inventory(request):
    try:
        member = request.user.company_member_profile
    except ObjectDoesNotExist:
        if not request.user.is_superuser:
            return render(request, "inventory/my_inventory_missing.html")
        form = CompanyMemberForm(request.POST or None, initial={
            "full_name": request.user.get_full_name() or request.user.username,
            "email": request.user.email,
        })
        if request.method == "POST" and form.is_valid():
            member = form.save(commit=False)
            member.user = request.user
            member.save()
            return redirect("inventory:my_inventory")
        return render(request, "inventory/form.html", {
            "form": form, "page_title": "Lengkapi Profil Inventaris Saya",
            "cancel_url": "inventory:dashboard",
        })
    return member_detail(request, pk=member.pk)


@inventory_required
def personal_item_create(request):
    try:
        member = request.user.company_member_profile
    except ObjectDoesNotExist:
        return redirect("inventory:my_inventory")
    initial = {}
    requested_category = request.GET.get("category")
    if requested_category in dict(InventoryItem.CATEGORY_CHOICES):
        initial["category"] = requested_category
    form = PersonalInventoryItemForm(request.POST if request.method == "POST" else None, request.FILES or None, initial=initial, section=category_section(requested_category))
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.asset_code = f"PRIBADI-{uuid4().hex[:10].upper()}"
        item.purchase_price = 0
        item.quantity = 1
        item.status = "assigned"
        item.assigned_to = member
        item.created_by = request.user
        item.updated_by = request.user
        item.save()
        InventoryActivity.objects.create(
            item=item, actor=request.user, action="created",
            description="Inventaris ditambahkan secara mandiri oleh pengguna.",
        )
        messages.success(request, "Inventaris Anda berhasil ditambahkan.")
        return redirect("inventory:member_detail", pk=member.pk)
    return render(request, "inventory/personal_item_form.html", {"form": form, "member": member})


@inventory_write_required
def member_create(request):
    form = CompanyMemberForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        member = form.save()
        messages.success(request, f"{member.full_name} berhasil ditambahkan.")
        return redirect("inventory:member_detail", pk=member.pk)
    return render(request, "inventory/form.html", {"form": form, "page_title": "Tambah Anggota Perusahaan", "cancel_url": "inventory:member_list"})


@inventory_write_required
def member_edit(request, pk):
    member = get_object_or_404(CompanyMember, pk=pk)
    form = CompanyMemberForm(request.POST or None, instance=member)
    if request.method == "POST" and form.is_valid():
        member = form.save()
        messages.success(request, "Data anggota berhasil diperbarui.")
        return redirect("inventory:member_detail", pk=member.pk)
    return render(request, "inventory/form.html", {"form": form, "page_title": "Edit Anggota Perusahaan", "cancel_url": "inventory:member_detail", "cancel_pk": member.pk})


@inventory_write_required
def item_list(request):
    items = InventoryItem.objects.select_related("assigned_to")
    search = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    status = request.GET.get("status", "").strip()
    condition = request.GET.get("condition", "").strip()
    if search:
        items = items.filter(Q(asset_code__icontains=search) | Q(item_name__icontains=search) | Q(serial_number__icontains=search) | Q(assigned_to__full_name__icontains=search))
    if category in dict(InventoryItem.CATEGORY_CHOICES):
        items = items.filter(category=category)
    if status in dict(InventoryItem.STATUS_CHOICES):
        items = items.filter(status=status)
    if condition in dict(InventoryItem.CONDITION_CHOICES):
        items = items.filter(condition=condition)
    return render(request, "inventory/item_list.html", {
        "page_obj": Paginator(items, 20).get_page(request.GET.get("page")),
        "categories": InventoryItem.CATEGORY_CHOICES, "statuses": InventoryItem.STATUS_CHOICES,
        "conditions": InventoryItem.CONDITION_CHOICES,
        "filters": {"q": search, "category": category, "status": status, "condition": condition},
    })


@inventory_required
def item_detail(request, pk):
    item = get_object_or_404(InventoryItem.objects.select_related("assigned_to"), pk=pk)
    if not request.can_edit_inventory:
        assigned_user_id = item.assigned_to.user_id if item.assigned_to else None
        if assigned_user_id != request.user.pk:
            raise PermissionDenied("Anda hanya dapat melihat inventaris milik sendiri.")
    item_reports = item.reports.all() if request.user.is_superuser else item.reports.filter(reporter=request.user)
    return render(request, "inventory/item_detail.html", {"item": item, "item_reports": item_reports})


@inventory_required
def item_photo(request, pk):
    item = get_object_or_404(InventoryItem.objects.select_related("assigned_to"), pk=pk)
    if not request.can_edit_inventory and not _participant_owns_item(request, item):
        raise PermissionDenied("Anda hanya dapat melihat foto inventaris milik sendiri.")
    if not item.photo:
        raise Http404("Foto belum tersedia.")
    try:
        response = FileResponse(item.photo.open("rb"), content_type="image/jpeg")
    except FileNotFoundError:
        raise Http404("Foto tidak ditemukan.")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@inventory_write_required
def item_create(request):
    initial = {}
    member_id = request.GET.get("member")
    requested_category = request.GET.get("category")
    if member_id:
        assigned_member = CompanyMember.objects.filter(pk=member_id).first()
        if assigned_member:
            initial.update({"assigned_to": assigned_member, "status": "assigned"})
    if requested_category in dict(InventoryItem.CATEGORY_CHOICES):
        initial["category"] = requested_category
    form = InventoryItemForm(request.POST if request.method == "POST" else None, request.FILES or None, initial=initial, section=category_section(requested_category))
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.created_by = request.user
        item.updated_by = request.user
        item.save()
        InventoryActivity.objects.create(item=item, actor=request.user, action="created", description="Barang inventaris dibuat.")
        messages.success(request, f"{item.asset_code} berhasil ditambahkan.")
        return redirect("inventory:item_detail", pk=item.pk)
    return render(request, "inventory/form.html", {
        "form": form,
        "page_title": "Tambah Barang Inventaris",
        "cancel_url": "inventory:item_list",
        "inventory_item_form": True,
        "basic_fields": [
            form["asset_code"], form["item_name"], form["category"],
            form["received_date"], form["condition"], form["status"],
            form["assigned_to"],
        ],
        "detail_fields": [
            form["brand"], form["model"],
            *([form["serial_number"]] if "serial_number" in form.fields else []), form["photo"],
            form["specifications"], form["purchase_price"], form["quantity"],
            form["location"], form["warranty_expiry"], form["notes"],
        ],
    })


@inventory_write_required
def item_edit(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    previous_user = item.assigned_to
    form = InventoryItemForm(request.POST if request.method == "POST" else None, request.FILES or None, instance=item, section=category_section(item.category))
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.updated_by = request.user
        item.save()
        description = "Data barang inventaris diperbarui."
        if previous_user != item.assigned_to:
            target = item.assigned_to.full_name if item.assigned_to else "tidak ada pengguna"
            description = f"Penanggung jawab diubah menjadi {target}."
        InventoryActivity.objects.create(item=item, actor=request.user, action="updated", description=description)
        messages.success(request, f"{item.asset_code} berhasil diperbarui.")
        return redirect("inventory:item_detail", pk=item.pk)
    return render(request, "inventory/form.html", {
        "form": form,
        "page_title": "Edit Barang Inventaris",
        "cancel_url": "inventory:item_detail",
        "cancel_pk": item.pk,
        "inventory_item_form": True,
        "basic_fields": [
            form["asset_code"], form["item_name"], form["category"],
            form["received_date"], form["condition"], form["status"],
            form["assigned_to"],
        ],
        "detail_fields": [
            form["brand"], form["model"],
            *([form["serial_number"]] if "serial_number" in form.fields else []), form["photo"],
            form["specifications"], form["purchase_price"], form["quantity"],
            form["location"], form["warranty_expiry"], form["notes"],
        ],
    })


def _participant_owns_item(request, item):
    return bool(item.assigned_to and item.assigned_to.user_id == request.user.pk)


@inventory_required
def report_list(request):
    reports = InventoryReport.objects.select_related("item", "reporter", "item__assigned_to")
    if not request.user.is_superuser:
        reports = reports.filter(reporter=request.user)
    status = request.GET.get("status", "").strip()
    if status in dict(InventoryReport.STATUS_CHOICES):
        reports = reports.filter(status=status)
    return render(request, "inventory/report_list.html", {
        "reports": reports,
        "statuses": InventoryReport.STATUS_CHOICES,
        "selected_status": status,
    })


@inventory_required
def report_create(request, item_pk=None):
    item = None
    if item_pk is not None:
        item = get_object_or_404(InventoryItem.objects.select_related("assigned_to"), pk=item_pk)
        if not request.can_edit_inventory and not _participant_owns_item(request, item):
            raise PermissionDenied("Anda hanya dapat melaporkan inventaris milik sendiri.")
        form = InventoryReportForm(request.POST or None)
    else:
        items = InventoryItem.objects.select_related("assigned_to")
        if not request.can_edit_inventory:
            items = items.filter(assigned_to__user=request.user)
        form = NewInventoryReportForm(request.POST or None, items=items)
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.item = item or form.cleaned_data["item"]
        report.reporter = request.user
        report.status = "reported"
        report.save()
        InventoryActivity.objects.create(
            item=report.item,
            actor=request.user,
            action="reported",
            description=f"Laporan {report.get_report_type_display().lower()} dibuat.",
        )
        messages.success(request, "Laporan berhasil dikirim kepada petugas inventaris.")
        return redirect("inventory:report_list")
    return render(request, "inventory/report_form.html", {"form": form, "item": item})


@inventory_required
def report_detail(request, pk):
    report = get_object_or_404(
        InventoryReport.objects.select_related("item", "reporter", "item__assigned_to"), pk=pk
    )
    if not request.user.is_superuser and report.reporter_id != request.user.pk:
        raise PermissionDenied("Anda hanya dapat melihat laporan yang Anda buat sendiri.")
    return render(request, "inventory/report_detail.html", {"report": report})


@inventory_required
def report_advance(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied("Hanya superuser yang dapat mengubah status laporan.")
    if request.method != "POST":
        raise PermissionDenied("Status laporan hanya dapat diubah melalui tombol tindakan.")
    report = get_object_or_404(InventoryReport.objects.select_related("item"), pk=pk)
    next_status = {
        "reported": "verified",
        "verified": "proposed",
        "proposed": "handed_over",
        "handed_over": "resolved",
    }.get(report.status)
    if next_status:
        report.status = next_status
        report.resolved_at = timezone.now() if next_status == "resolved" else None
        report.save(update_fields=["status", "resolved_at", "updated_at"])
        InventoryActivity.objects.create(
            item=report.item,
            actor=request.user,
            action="report_updated",
            description=f"Status laporan kerusakan menjadi {report.get_status_display()}.",
        )
        messages.success(request, f"Status laporan menjadi {report.get_status_display()}.")
    return redirect("inventory:report_list")
