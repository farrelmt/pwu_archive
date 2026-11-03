from io import BytesIO

from PIL import Image, ImageOps
from django import forms
from django.core.files.base import ContentFile

from .models import InternetPackageHistory, InternetSimCard, InventoryItem, InventoryReport
from .codes import asset_code_for_ownership
from .credentials import encrypt_software_password


FIELD_CLASS = (
    "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 "
    "text-sm focus:border-violet-500 focus:outline-none focus:ring-4 focus:ring-violet-100"
)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = FIELD_CLASS
            if isinstance(field.widget, forms.Select) and not isinstance(field.widget, forms.SelectMultiple):
                field.widget.attrs["class"] += " inventory-form-select"



HARDWARE_CATEGORIES = {"computer", "laptop", "peripheral", "component", "network", "modem_wifi", "hardware"}
GENERAL_CATEGORIES = {"furniture", "vehicle", "tool", "office", "other"}
ITEM_TYPE_CHOICES = [
    ("inventaris", "Inventaris"),
    ("hardware", "Hardware"),
    ("software", "Software"),
]
DEFAULT_CATEGORY_BY_TYPE = {"inventaris": "office", "hardware": "computer", "software": "software"}
ROOM_CHOICES = tuple(sorted((
    "Dapur",
    "Garasi",
    "Gudang",
    "Hall",
    "Meja IT",
    "Musholla",
    "Pos",
    "Rumah Ketiga",
    "Ruang Direktur Utama",
    "Ruang Direktur",
    "Ruang Akuntansi",
    "Ruang Aset",
    "Ruang Keuangan",
    "Ruang Umum & Legal",
    "Ruang Manajemen Risiko",
    "Ruang Sekretaris",
    "Ruang SPI",
    "Ruang Komisaris",
    "Ruang Rapat",
    "Ruang Humas",
    "Ruang HRD",
    "Ruang Wirajatim KSO",
    "Ruang Administrator Sistem",
    "Ruang Lainnya",
), key=str.casefold))


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
        requested_type = self.data.get("item_type") if self.is_bound and "item_type" in self.data else None
        category = self.data.get("category") if self.is_bound else self.initial.get("category")
        self.section = requested_type or section or category_section(category) or "inventaris"
        self.fields["item_type"].initial = self.section
        if self.section == "software":
            self.fields["serial_number"].label = "Nomor lisensi"
            self.fields["item_name"].label = "Nama Software"
            self.fields["brand"].label = "Developer / Distributor"
            self.fields["model"].label = "Versi Software"
            self.fields["specifications"].label = "Spesifikasi Software / Lisensi"
            self.fields["purchase_price"].label = "Harga lisensi / langganan (Rp)"
            if "quantity" in self.fields:
                self.fields["quantity"].label = "Jumlah lisensi / pengguna"
            if "warranty_expiry" in self.fields:
                self.fields["warranty_expiry"].label = "Tanggal berakhir lisensi"
        for name, field in self.fields.items():
            field.required = name == "item_name"
        if "location" in self.fields:
            current_location = self.instance.location or self.initial.get("location") or ""
            rooms = list(ROOM_CHOICES)
            if current_location and current_location not in ROOM_CHOICES:
                rooms.append(current_location)
            choices = [("", "Pilih ruangan")] + [
                (room, f"{room} (lokasi sebelumnya)" if room == current_location and room not in ROOM_CHOICES else room)
                for room in sorted(rooms, key=str.casefold)
            ]
            self.fields["location"] = forms.ChoiceField(
                label="Lokasi / Ruangan", required=False, choices=choices,
                widget=forms.Select(attrs={
                    "class": FIELD_CLASS + " inventory-form-select inventory-location-select",
                    "aria-describedby": "inventory-location-help",
                }),
            )
        self.fields["photo"].widget = PhotoInput(attrs={"class": FIELD_CLASS})
        self.fields["photo"].help_text = "Opsional. JPG, PNG, atau WebP, maksimal 5 MB. Foto disimpan di server setelah Anda menekan Simpan."
        self.fields["photo"].widget.attrs["accept"] = "image/jpeg,image/png,image/webp"
        self.fields["software_password"].widget.attrs["class"] = FIELD_CLASS
        self.fields["software_password_clear"].widget.attrs["class"] = (
            "h-4 w-4 rounded border-slate-300 text-violet-700 focus:ring-violet-500"
        )
        for name in ("received_date_same_as_purchase", "purchase_date_unknown"):
            self.fields[name].widget.attrs["class"] = (
                "h-4 w-4 rounded border-slate-300 text-violet-700 focus:ring-violet-500"
            )
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
        item_type = cleaned.get("item_type") or self.section
        if item_type not in DEFAULT_CATEGORY_BY_TYPE:
            item_type = "inventaris"
        cleaned["item_type"] = item_type
        category = cleaned.get("category")
        if not category:
            initial_category = self.initial.get("category")
            category = initial_category if category_section(initial_category) == item_type else DEFAULT_CATEGORY_BY_TYPE[item_type]
            cleaned["category"] = category
        elif category_section(category) != item_type:
            self.add_error("category", "Pilih kategori yang sesuai dengan jenis barang.")
        defaults = {"condition": "good", "status": "stock", "ownership": "company", "purchase_price": 0, "quantity": 1}
        for name, default in defaults.items():
            if name in self.fields and name not in self.errors and cleaned.get(name) in (None, ""):
                cleaned[name] = self.initial.get(name) or default
        if cleaned.get("purchase_date_unknown"):
            cleaned["purchase_date"] = None
            cleaned["received_date_same_as_purchase"] = False
        elif cleaned.get("received_date_same_as_purchase"):
            if cleaned.get("purchase_date"):
                cleaned["received_date"] = cleaned["purchase_date"]
            else:
                self.add_error("purchase_date", "Isi tanggal pembelian terlebih dahulu.")
        if "asset_code" in self.fields:
            cleaned["asset_code"] = asset_code_for_ownership(
                cleaned.get("ownership") or "company",
                cleaned.get("asset_code") or self.instance.asset_code,
            )
        if item_type == "inventaris":
            cleaned["serial_number"] = ""
        if item_type == "software":
            if cleaned.get("software_billing_type") != "subscription":
                cleaned["software_billing_cycle"] = ""
                cleaned["software_renewal_date"] = None
        else:
            cleaned["software_billing_type"] = ""
            cleaned["software_billing_cycle"] = ""
            cleaned["software_payment_method"] = ""
            cleaned["software_renewal_date"] = None
        if cleaned.get("ownership") == "third_party":
            name = (cleaned.get("third_party_name") or "").strip()
            if not name:
                self.add_error("third_party_name", "Isi nama pemilik pihak ketiga.")
            cleaned["third_party_name"] = name
        else:
            cleaned["third_party_name"] = ""
        return cleaned

    def save(self, commit=True):
        item = super().save(commit=False)
        if item.category == "software":
            item.location = ""
            item.photo = ""
            item.condition = "good"
            password = self.cleaned_data.get("software_password")
            if password:
                item.software_password_encrypted = encrypt_software_password(password)
            elif self.cleaned_data.get("software_password_clear"):
                item.software_password_encrypted = None
        else:
            item.software_username = None
            item.software_email = None
            item.software_password_encrypted = None
            item.software_billing_type = ""
            item.software_billing_cycle = ""
            item.software_payment_method = ""
            item.software_renewal_date = None
        if commit:
            item.save()
            self.save_m2m()
        return item


class InventoryItemForm(ItemFormMixin, StyledModelForm):
    item_type = forms.ChoiceField(label="Jenis barang", choices=ITEM_TYPE_CHOICES, required=False)
    software_password = forms.CharField(
        label="Password akun", required=False, max_length=500,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Opsional. Kosongkan saat mengedit untuk mempertahankan password yang tersimpan.",
    )
    software_password_clear = forms.BooleanField(label="Hapus password tersimpan", required=False)

    class Meta:
        model = InventoryItem
        fields = [
            "asset_code", "item_name", "category", "brand", "model",
            "serial_number", "specifications", "purchase_date", "received_date",
            "purchase_date_unknown", "received_date_same_as_purchase",
            "purchase_price", "quantity", "condition", "status", "ownership",
            "third_party_name", "location",
            "software_username", "software_email",
            "software_billing_type", "software_billing_cycle", "software_payment_method", "software_renewal_date",
            "assigned_to", "warranty_expiry", "notes", "photo",
        ]
        widgets = {
            "specifications": forms.Textarea(attrs={"rows": 4}),
            "purchase_date": CalendarDateInput(),
            "received_date": CalendarDateInput(),
            "warranty_expiry": CalendarDateInput(),
            "software_renewal_date": CalendarDateInput(),
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
    item_type = forms.ChoiceField(label="Jenis barang", choices=ITEM_TYPE_CHOICES, required=False)
    software_password = forms.CharField(
        label="Password akun", required=False, max_length=500,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Opsional. Kosongkan saat mengedit untuk mempertahankan password yang tersimpan.",
    )
    software_password_clear = forms.BooleanField(label="Hapus password tersimpan", required=False)

    class Meta:
        model = InventoryItem
        fields = [
            "item_name", "category", "brand", "model", "serial_number",
            "specifications", "purchase_date", "received_date",
            "purchase_date_unknown", "received_date_same_as_purchase",
            "condition", "ownership",
            "third_party_name", "location", "software_username", "software_email",
            "software_billing_type", "software_billing_cycle", "purchase_price",
            "software_payment_method", "software_renewal_date",
            "notes", "photo",
        ]
        widgets = {
            "specifications": forms.Textarea(attrs={"rows": 3}),
            "purchase_date": CalendarDateInput(),
            "received_date": CalendarDateInput(),
            "software_renewal_date": CalendarDateInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("category") != "software":
            cleaned["purchase_price"] = 0
        return cleaned


class InternetSimCardForm(StyledModelForm):
    class Meta:
        model = InternetSimCard
        fields = ["sim_number", "operator", "person_in_charge"]
        help_texts = {
            "sim_number": "Nomor telepon pada kartu SIM.",
            "person_in_charge": "Nama orang yang bertanggung jawab atas nomor ini.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sim_number"].required = True


class InternetPackageForm(StyledModelForm):
    sim_card = forms.ModelChoiceField(
        label="Kartu SIM", queryset=InternetSimCard.objects.none(),
        empty_label="Pilih kartu SIM", required=True,
    )

    def __init__(self, *args, item, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sim_card"].queryset = item.sim_cards.all()

    class Meta:
        model = InternetPackageHistory
        fields = [
            "sim_card", "package_name", "effective_on", "expires_on", "notes",
        ]
        widgets = {
            "effective_on": CalendarDateInput(),
            "expires_on": CalendarDateInput(),
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
