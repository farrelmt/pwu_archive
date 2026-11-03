import base64

from django import forms
from django.contrib.staticfiles import finders
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from weasyprint import HTML

from accounts.directory import MEMBER_DIVISION_ORDER

from .access import inventory_required
from .models import CompanyMember, InventoryRequest


class RequestForm(forms.Form):
    request_type = forms.ChoiceField(label="Jenis permintaan", choices=InventoryRequest.TYPE_CHOICES)
    submitted_on = forms.DateField(label="Tanggal pengajuan", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), input_formats=["%Y-%m-%d"])
    applicant_name = forms.ChoiceField(label="Nama lengkap")
    division = forms.ChoiceField(label="Divisi")
    purpose = forms.CharField(label="Keperluan", widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        member = getattr(user, "company_member_profile", None)
        current_name = member.full_name if member else user.get_full_name() or user.username
        current_division = member.division if member else ""
        if current_division == "Administrator Sistem":
            current_division = "Divisi Umum & Legal"
        names = set(CompanyMember.objects.exclude(full_name="").values_list("full_name", flat=True))
        names.add(current_name)
        divisions = set(MEMBER_DIVISION_ORDER)
        divisions.update(CompanyMember.objects.exclude(division="").values_list("division", flat=True))
        divisions.discard("Administrator Sistem")
        if current_division:
            divisions.add(current_division)
        self.fields["applicant_name"].choices = [(name, name) for name in sorted(names, key=str.casefold)]
        self.fields["division"].choices = [(division, division) for division in sorted(divisions, key=str.casefold)]
        self.fields["submitted_on"].initial = timezone.localdate()
        self.fields["applicant_name"].initial = current_name
        self.fields["division"].initial = current_division
        for number in range(1, 6):
            required = number == 1
            for key, label in (("description", "Deskripsi"), ("stock", "Stok Tersedia"),
                               ("quantity", "Jumlah Permintaan"), ("unit", "Satuan"),
                               ("notes", "Spesifikasi/Keterangan")):
                self.fields[f"{key}_{number}"] = forms.CharField(
                    label=label, required=required and key in {"description", "quantity", "unit"},
                    max_length=500,
                )
        for name, field in self.fields.items():
            field.widget.attrs["class"] = (
                "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 "
                "shadow-sm focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-100"
            )
            if name.startswith(("stock_", "quantity_", "unit_")):
                field.widget.attrs["class"] += " px-1 text-center"
                field.widget.attrs["style"] = "padding-left: 0.25rem; padding-right: 0.25rem;"
            if name.startswith(("description_", "stock_", "quantity_", "unit_", "notes_")):
                field.widget.attrs["aria-label"] = f"Baris {name.rsplit('_', 1)[1]} {field.label}"
                field.widget.attrs["placeholder"] = {
                    "description": "Nama barang / jasa",
                    "stock": "0",
                    "quantity": "1",
                    "unit": "pcs",
                    "notes": "Spesifikasi tambahan",
                }[name.rsplit("_", 1)[0]]

    def clean(self):
        data = super().clean()
        for number in range(2, 6):
            values = [data.get(f"{key}_{number}") for key in ("description", "stock", "quantity", "unit", "notes")]
            if any(values):
                for key in ("description", "quantity", "unit"):
                    if not data.get(f"{key}_{number}"):
                        self.add_error(f"{key}_{number}", "Wajib diisi untuk baris yang digunakan.")
        return data

    def item_rows(self):
        return [dict(description=self.cleaned_data[f"description_{n}"],
                     stock=self.cleaned_data.get(f"stock_{n}", ""),
                     quantity=self.cleaned_data[f"quantity_{n}"],
                     unit=self.cleaned_data[f"unit_{n}"],
                     notes=self.cleaned_data.get(f"notes_{n}", ""))
                for n in range(1, 6) if self.cleaned_data.get(f"description_{n}")]


@inventory_required
@require_http_methods(["GET", "POST"])
def request_create(request, item_pk=None):
    form = RequestForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        entry = InventoryRequest.objects.create(
            requester=request.user, request_type=form.cleaned_data["request_type"],
            purpose=form.cleaned_data["purpose"], items=form.item_rows(),
            submitted_on=form.cleaned_data["submitted_on"],
            applicant_name=form.cleaned_data["applicant_name"],
            division=form.cleaned_data["division"],
        )
        return redirect("inventory:request_detail", public_id=entry.public_id)
    rows = [[form[f"{key}_{number}"] for key in ("description", "stock", "quantity", "unit", "notes")]
            for number in range(1, 6)]
    return render(request, "inventory/request_form.html", {"form": form, "rows": rows})


def _entry(request, public_id):
    entry = get_object_or_404(InventoryRequest, public_id=public_id)
    if not request.can_manage_inventory and entry.requester_id != request.user.pk:
        raise PermissionDenied("Anda hanya dapat melihat permintaan sendiri.")
    return entry


@inventory_required
def request_list(request):
    entries = InventoryRequest.objects.all() if request.can_manage_inventory else InventoryRequest.objects.filter(requester=request.user)
    return render(request, "inventory/request_list.html", {"entries": entries})


@inventory_required
def request_detail(request, public_id):
    return render(request, "inventory/request_detail.html", {"entry": _entry(request, public_id)})


@inventory_required
def request_download(request, public_id):
    entry = _entry(request, public_id)
    rows = list(entry.items)[:5]
    rows.extend({} for _ in range(5 - len(rows)))
    logo_path = finders.find("images/wirajatim-logo-horizontal.png")
    with open(logo_path, "rb") as logo_file:
        logo_data = "data:image/png;base64," + base64.b64encode(logo_file.read()).decode("ascii")
    font_path = finders.find("fonts/Lato-Semibold.ttf")
    with open(font_path, "rb") as font_file:
        title_font_data = "data:font/truetype;base64," + base64.b64encode(font_file.read()).decode("ascii")
    html = render_to_string("inventory/request_pdf.html", {
        "entry": entry, "rows": rows, "date": entry.submitted_on, "logo_data": logo_data, "title_font_data": title_font_data,
    })
    pdf = HTML(string=html).write_pdf()
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="permintaan-{entry.pk}.pdf"'
    return response
