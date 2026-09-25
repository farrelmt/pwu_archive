from django import forms

from .models import CompanyMember, InventoryItem


FIELD_CLASS = (
    "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 "
    "text-sm focus:border-violet-500 focus:outline-none focus:ring-4 focus:ring-violet-100"
)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = FIELD_CLASS


class CompanyMemberForm(StyledModelForm):
    class Meta:
        model = CompanyMember
        fields = [
            "employee_id", "full_name", "email", "phone", "division",
            "position", "join_date", "status", "notes",
        ]
        widgets = {
            "join_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class InventoryItemForm(StyledModelForm):
    class Meta:
        model = InventoryItem
        fields = [
            "asset_code", "item_name", "category", "brand", "model",
            "serial_number", "specifications", "received_date",
            "purchase_price", "quantity", "condition", "status", "location",
            "assigned_to", "warranty_expiry", "notes",
        ]
        widgets = {
            "specifications": forms.Textarea(attrs={"rows": 4}),
            "received_date": forms.DateInput(attrs={"type": "date"}),
            "warranty_expiry": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == "assigned" and not cleaned.get("assigned_to"):
            self.add_error("assigned_to", "Pilih pengguna untuk barang berstatus Digunakan.")
        return cleaned
