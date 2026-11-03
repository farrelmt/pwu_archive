import uuid

from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class InventoryAccess(models.Model):
    ROLE_CHOICES = [
        ("manager", "Manajer Inventaris"),
        ("officer", "Petugas Inventaris"),
        ("participant", "Peserta Inventaris"),
    ]
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_access",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Hak akses inventaris"
        verbose_name_plural = "Hak akses inventaris"

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


class CompanyMember(models.Model):
    STATUS_CHOICES = [
        ("active", "Aktif"),
        ("inactive", "Tidak Aktif"),
        ("resigned", "Keluar"),
    ]
    employee_id = models.CharField("NIP/NIK", max_length=50, unique=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="company_member_profile",
        blank=True,
        null=True,
    )
    full_name = models.CharField("Nama lengkap", max_length=180)
    email = models.EmailField(blank=True)
    phone = models.CharField("Nomor telepon", max_length=30, blank=True)
    division = models.CharField("Divisi", max_length=120)
    position = models.CharField("Jabatan", max_length=120)
    join_date = models.DateField("Tanggal bergabung", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    notes = models.TextField("Catatan", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [models.Index(fields=["division", "status"], name="inv_member_div_status_idx")]
        verbose_name = "Anggota perusahaan"
        verbose_name_plural = "Anggota perusahaan"

    def __str__(self):
        return f"{self.employee_id} - {self.full_name}"


def inventory_photo_path(instance, filename):
    return f"inventory/photos/{uuid4().hex}.jpg"


class InventoryItem(models.Model):
    OWNERSHIP_CHOICES = [
        ("company", "Company"),
        ("lumbung", "Lumbung"),
        ("personal", "Personal"),
        ("third_party", "Third Party"),
    ]
    CATEGORY_CHOICES = [
        ("computer", "Komputer"),
        ("laptop", "Laptop"),
        ("peripheral", "Periferal IT (Keyboard, Mouse, Monitor)"),
        ("component", "Komponen Hardware"),
        ("network", "Perangkat Jaringan"),
        ("modem_wifi", "Modem/Wifi"),
        ("software", "Software / Lisensi"),
        ("hardware", "Perangkat Keras Lainnya"),
        ("furniture", "Furnitur"),
        ("vehicle", "Kendaraan"),
        ("tool", "Peralatan Kerja"),
        ("office", "Perlengkapan Kantor"),
        ("other", "Lainnya"),
    ]
    CONDITION_CHOICES = [
        ("new", "Baru"),
        ("good", "Baik"),
        ("fair", "Cukup"),
        ("damaged", "Rusak"),
    ]
    STATUS_CHOICES = [
        ("stock", "Tersedia"),
        ("assigned", "Digunakan"),
        ("maintenance", "Perbaikan"),
        ("retired", "Tidak Digunakan"),
        ("lost", "Hilang"),
    ]

    asset_code = models.CharField("Kode aset", max_length=50, unique=True)
    item_name = models.CharField("Nama barang", max_length=180)
    category = models.CharField("Kategori", max_length=20, choices=CATEGORY_CHOICES)
    brand = models.CharField("Merek", max_length=100, blank=True)
    model = models.CharField("Model/Tipe", max_length=120, blank=True)
    serial_number = models.CharField("Nomor seri", max_length=120, blank=True, db_index=True)
    specifications = models.TextField("Spesifikasi", blank=True)
    received_date = models.DateField("Tanggal diterima", blank=True, null=True)
    purchase_date = models.DateField("Tanggal pembelian", blank=True, null=True)
    purchase_date_unknown = models.BooleanField(
        "Tanggal pembelian tidak diketahui", default=False
    )
    received_date_same_as_purchase = models.BooleanField(
        "Tanggal diterima sama dengan tanggal pembelian", default=False
    )
    photo = models.ImageField("Foto barang", upload_to=inventory_photo_path, blank=True)
    purchase_price = models.DecimalField(
        "Harga satuan", max_digits=16, decimal_places=2,
        validators=[MinValueValidator(0)], default=0,
    )
    quantity = models.PositiveIntegerField("Jumlah", default=1, validators=[MinValueValidator(1)])
    condition = models.CharField("Kondisi", max_length=20, choices=CONDITION_CHOICES, default="good")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="stock")
    ownership = models.CharField("Kepemilikan", max_length=20, choices=OWNERSHIP_CHOICES, default="company")
    third_party_name = models.CharField("Nama pihak ketiga", max_length=180, blank=True)
    location = models.CharField("Lokasi", max_length=160, blank=True)
    software_username = models.CharField("Username akun", max_length=180, blank=True, null=True)
    software_email = models.EmailField("Email akun", blank=True, null=True)
    software_password_encrypted = models.TextField(blank=True, null=True, editable=False)
    SOFTWARE_BILLING_CHOICES = [("one_time", "Sekali bayar"), ("subscription", "Langganan")]
    SOFTWARE_BILLING_CYCLE_CHOICES = [("monthly", "Bulanan"), ("yearly", "Tahunan"), ("other", "Lainnya")]
    software_billing_type = models.CharField("Jenis biaya", max_length=20, choices=SOFTWARE_BILLING_CHOICES, blank=True)
    software_billing_cycle = models.CharField("Periode langganan", max_length=20, choices=SOFTWARE_BILLING_CYCLE_CHOICES, blank=True)
    software_payment_method = models.CharField("Cara pembayaran", max_length=120, blank=True)
    software_renewal_date = models.DateField("Tanggal perpanjangan berikutnya", blank=True, null=True)
    assigned_to = models.ForeignKey(
        CompanyMember, on_delete=models.PROTECT, related_name="inventory_items",
        blank=True, null=True, verbose_name="Pengguna/Penanggung jawab",
    )
    warranty_expiry = models.DateField("Garansi berakhir", blank=True, null=True)
    notes = models.TextField("Catatan", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_inventory_items"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="updated_inventory_items"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["item_name", "asset_code"]
        indexes = [
            models.Index(fields=["category", "status"], name="inv_item_cat_status_idx"),
            models.Index(fields=["assigned_to", "status"], name="inv_item_owner_status_idx"),
        ]
        verbose_name = "Barang inventaris"
        verbose_name_plural = "Barang inventaris"

    @property
    def total_value(self):
        return self.purchase_price * self.quantity

    def clean(self):
        super().clean()
        if self.ownership == "third_party" and not (self.third_party_name or "").strip():
            raise ValidationError({"third_party_name": "Isi nama pemilik pihak ketiga."})

    def __str__(self):
        return f"{self.asset_code} - {self.item_name}"


class InventoryActivity(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=40)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Aktivitas inventaris"


class InternetSimCard(models.Model):
    item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT, related_name="sim_cards",
        verbose_name="Router / modem",
    )
    sim_number = models.CharField("Nomor SIM", max_length=40, blank=True)
    operator = models.CharField("Operator", max_length=100, blank=True)
    person_in_charge = models.CharField("Penanggung jawab nomor", max_length=180, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sim_number", "pk"]
        verbose_name = "Kartu SIM internet"
        verbose_name_plural = "Kartu SIM internet"

    def __str__(self):
        label = self.sim_number or "Nomor belum diketahui"
        parts = [label, self.operator, self.person_in_charge]
        return " · ".join(part for part in parts if part)


class InternetPackageHistory(models.Model):
    item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT, related_name="internet_packages",
        verbose_name="Router / modem",
    )
    sim_card = models.ForeignKey(
        InternetSimCard, on_delete=models.PROTECT, related_name="package_history",
        verbose_name="Kartu SIM", blank=True, null=True,
    )
    # Snapshots preserve the SIM details shown when this package was recorded.
    sim_number = models.CharField("Nomor SIM", max_length=40, blank=True)
    operator = models.CharField("Operator", max_length=100, blank=True)
    person_in_charge = models.CharField("Penanggung jawab nomor", max_length=180, blank=True)
    package_name = models.CharField("Paket internet", max_length=180)
    effective_on = models.DateField("Mulai berlaku", default=timezone.localdate)
    expires_on = models.DateField("Batas berlaku")
    notes = models.TextField("Catatan", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_on", "-created_at", "-pk"]
        indexes = [models.Index(fields=["item", "-effective_on"], name="inv_pkg_item_date_idx")]
        verbose_name = "Riwayat paket internet"
        verbose_name_plural = "Riwayat paket internet"

    def clean(self):
        super().clean()
        if self.effective_on and self.expires_on and self.expires_on < self.effective_on:
            raise ValidationError({"expires_on": "Batas berlaku tidak boleh sebelum tanggal mulai."})

    @property
    def is_expired(self):
        return bool(self.expires_on and self.expires_on < timezone.localdate())

    def __str__(self):
        return f"{self.item.asset_code} - {self.package_name}"


class InventoryReport(models.Model):
    REPORT_TYPE_CHOICES = [
        ("damaged", "Barang Rusak"),
        ("complaint", "Keluhan Penggunaan"),
        ("other", "Masalah Lainnya"),
    ]
    STATUS_CHOICES = [
        ("reported", "Laporan"),
        ("verified", "Verifikasi"),
        ("proposed", "Pengajuan"),
        ("handed_over", "Penyerahan"),
        ("resolved", "Selesai"),
    ]

    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="reports",
        verbose_name="Barang inventaris",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="inventory_reports", verbose_name="Pelapor",
    )
    report_type = models.CharField("Jenis laporan", max_length=20, choices=REPORT_TYPE_CHOICES)
    description = models.TextField("Keluhan atau kerusakan")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="reported")
    resolution_note = models.TextField("Tindak lanjut", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="inv_report_status_idx"),
            models.Index(fields=["item", "status"], name="inv_report_item_idx"),
        ]
        verbose_name = "Laporan inventaris"
        verbose_name_plural = "Laporan inventaris"

    def __str__(self):
        return f"{self.item.asset_code} - {self.get_report_type_display()}"


def generate_request_public_id():
    return uuid.uuid4().hex


class InventoryRequest(models.Model):
    TYPE_CHOICES = [("procurement", "Pengadaan Barang / Jasa"), ("repair", "Perbaikan Barang")]
    public_id = models.CharField(max_length=32, unique=True, default=generate_request_public_id, editable=False)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="inventory_requests")
    request_type = models.CharField("Jenis permintaan", max_length=20, choices=TYPE_CHOICES)
    purpose = models.TextField("Keperluan")
    items = models.JSONField("Daftar barang / jasa", default=list)
    applicant_name = models.CharField("Nama lengkap", max_length=180)
    division = models.CharField("Divisi", max_length=120, blank=True)
    submitted_on = models.DateField("Tanggal pengajuan", default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Permintaan"
        verbose_name_plural = "Permintaan"
