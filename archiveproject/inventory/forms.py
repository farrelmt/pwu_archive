from io import BytesIO
from uuid import uuid4

from PIL import Image, ImageOps
from django import forms
from django.core.files.base import ContentFile

from .models import InventoryItem, InventoryReport


FIELD_CLASS = (
    "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 "
    "text-sm focus:border-violet-500 focus:outline-none focus:ring-4 focus:ring-violet-100"
)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = FIELD_CLASS



HARDWARE_CATEGORIES = {"computer", "laptop", "peripheral", "component", "network", "hardware"}
GENERAL_CATEGORIES = {"furniture", "vehicle", "tool", "office", "other"}


def category_section(category):
    if category == "software":
        return "software"
    if category in HARDWARE_CATEGORIES:
        return "hardware"
    if category in GENERAL_CATEGORIES:
        return "inventaris"
    return None


class CalendarDateInput(forms.DateInput):
    template_name = "inventory/widgets/date.html"

    def __init__(self, attrs=None):
        super().__init__(attrs={"type": "date", **(attrs or {})}, format="%Y-%m-%d")


class PhotoInput(forms.ClearableFileInput):
    template_name = "inventory/widgets/photo.html"


class ItemFormMixin:
    def __init__(self, *args, section=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.section = section
        categories = {"hardware": HARDWARE_CATEGORIES, "software": {"software"}, "inventaris": GENERAL_CATEGORIES}.get(section)
        if categories:
            self.fields["category"].choices = [choice for choice in InventoryItem.CATEGORY_CHOICES if choice[0] in categories]
        if section == "inventaris":
            self.fields.pop("serial_number", None)
        if section == "software" and "serial_number" in self.fields:
            self.fields["serial_number"].label = "Nomor lisensi"
        for name, field in self.fields.items():
            field.required = name == "item_name"
        self.fields["photo"].widget = PhotoInput(attrs={"class": FIELD_CLASS})
        self.fields["photo"].help_text = "Opsional. JPG, PNG, atau WebP, maksimal 5 MB. Foto disimpan di server setelah Anda menekan Simpan."
        self.fields["photo"].widget.attrs["accept"] = "image/jpeg,image/png,image/webp"
        if "asset_code" in self.fields:
            self.fields["asset_code"].help_text = "Boleh kosong; kode aset akan dibuat otomatis."

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if not photo or not hasattr(photo, "content_type"):
            return photo
        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Ukuran foto maksimal 5 MB.")
        with Image.open(photo) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise forms.ValidationError("Gunakan foto JPG, PNG, atau WebP.")
            if image.width * image.height > 25000000:
                raise forms.ValidationError("Resolusi foto terlalu besar (maksimal 25 megapiksel).")
            image = ImageOps.exif_transpose(image)
            image.thumbnail((2400, 2400))
            output = BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=85)
        return ContentFile(output.getvalue(), name="photo.jpg")

    def clean(self):
        cleaned = super().clean()
        defaults = {"category": {"hardware": "computer", "software": "software", "inventaris": "office"}.get(self.section, "other"), "condition": "good", "status": "stock", "purchase_price": 0, "quantity": 1}
        for name, default in defaults.items():
            if name in self.fields and name not in self.errors and cleaned.get(name) in (None, ""):
                cleaned[name] = self.initial.get(name) or default
        if "asset_code" in self.fields and not cleaned.get("asset_code"):
            cleaned["asset_code"] = self.instance.asset_code or f"INV-{uuid4().hex[:12].upper()}"
        if category_section(cleaned.get("category")) == "inventaris":
            cleaned["serial_number"] = ""
        return cleaned


class InventoryItemForm(ItemFormMixin, StyledModelForm):
    class Meta:
        model = InventoryItem
        fields = [
            "asset_code", "item_name", "category", "brand", "model",
            "serial_number", "specifications", "received_date",
            "purchase_price", "quantity", "condition", "status", "location",
            "assigned_to", "warranty_expiry", "notes", "photo",
        ]
        widgets = {
            "specifications": forms.Textarea(attrs={"rows": 4}),
            "received_date": CalendarDateInput(),
            "warranty_expiry": CalendarDateInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "model": "Versi software atau tipe/model perangkat.",
            "serial_number": "Nomor lisensi software atau nomor seri perangkat.",
            "specifications": "Misalnya prosesor, RAM, penyimpanan, sistem operasi, atau detail lisensi.",
            "warranty_expiry": "Untuk software, dapat digunakan sebagai tanggal berakhir lisensi.",
            "assigned_to": "Pilih pegawai yang menggunakan barang atau software ini.",
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == "assigned" and not cleaned.get("assigned_to"):
            self.add_error("assigned_to", "Pilih pengguna untuk barang berstatus Digunakan.")
        return cleaned


class PersonalInventoryItemForm(ItemFormMixin, StyledModelForm):
    class Meta:
        model = InventoryItem
        fields = [
            "item_name", "category", "brand", "model", "serial_number",
            "specifications", "received_date", "condition", "notes", "photo",
        ]
        widgets = {
            "specifications": forms.Textarea(attrs={"rows": 3}),
            "received_date": CalendarDateInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class InventoryReportForm(StyledModelForm):
    class Meta:
        model = InventoryReport
        fields = ["report_type", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}


class NewInventoryReportForm(InventoryReportForm):
    item = forms.ModelChoiceField(queryset=InventoryItem.objects.none(), label="Barang yang rusak")

    def __init__(self, *args, items, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = items
        self.order_fields(["item", "report_type", "description"])
