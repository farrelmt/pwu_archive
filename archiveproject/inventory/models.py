from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


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


class InventoryItem(models.Model):
    CATEGORY_CHOICES = [
        ("hardware", "Perangkat Keras"),
        ("software", "Perangkat Lunak"),
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
    received_date = models.DateField("Tanggal diterima")
    purchase_price = models.DecimalField(
        "Harga satuan", max_digits=16, decimal_places=2,
        validators=[MinValueValidator(0)], default=0,
    )
    quantity = models.PositiveIntegerField("Jumlah", default=1, validators=[MinValueValidator(1)])
    condition = models.CharField("Kondisi", max_length=20, choices=CONDITION_CHOICES, default="good")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="stock")
    location = models.CharField("Lokasi", max_length=160, blank=True)
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
