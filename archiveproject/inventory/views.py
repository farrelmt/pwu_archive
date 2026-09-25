from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .access import inventory_required, inventory_write_required
from .forms import CompanyMemberForm, InventoryItemForm
from .models import CompanyMember, InventoryActivity, InventoryItem


@inventory_required
def dashboard(request):
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


@inventory_required
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
    return render(request, "inventory/member_detail.html", {"member": member})


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


@inventory_required
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
    return render(request, "inventory/item_detail.html", {"item": item})


@inventory_write_required
def item_create(request):
    form = InventoryItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.created_by = request.user
        item.updated_by = request.user
        item.save()
        InventoryActivity.objects.create(item=item, actor=request.user, action="created", description="Barang inventaris dibuat.")
        messages.success(request, f"{item.asset_code} berhasil ditambahkan.")
        return redirect("inventory:item_detail", pk=item.pk)
    return render(request, "inventory/form.html", {"form": form, "page_title": "Tambah Barang Inventaris", "cancel_url": "inventory:item_list"})


@inventory_write_required
def item_edit(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    previous_user = item.assigned_to
    form = InventoryItemForm(request.POST or None, instance=item)
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
    return render(request, "inventory/form.html", {"form": form, "page_title": "Edit Barang Inventaris", "cancel_url": "inventory:item_detail", "cancel_pk": item.pk})
