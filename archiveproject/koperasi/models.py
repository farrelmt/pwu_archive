from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum


MONEY_VALIDATORS = [MinValueValidator(Decimal("0.01"))]


class Company(models.Model):
    TYPE_CHOICES = [
        ("holding", "Perusahaan Induk"),
        ("subsidiary", "Anak Perusahaan"),
    ]

    code = models.CharField("Kode", max_length=20, unique=True)
    name = models.CharField("Nama perusahaan", max_length=200)
    company_type = models.CharField(
        "Jenis perusahaan",
        max_length=20,
        choices=TYPE_CHOICES,
        default="subsidiary",
    )
    registration_number = models.CharField(
        "Nomor badan hukum", max_length=100, blank=True
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField("Alamat", blank=True)
    is_active = models.BooleanField("Aktif", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_type", "name"]
        verbose_name = "Perusahaan"
        verbose_name_plural = "Perusahaan"

    def __str__(self):
        return f"{self.code} - {self.name}"


class KoperasiAccess(models.Model):
    ROLE_CHOICES = [
        ("admin", "Administrator Koperasi"),
        ("manager", "Manajer Koperasi"),
        ("finance", "Keuangan"),
        ("officer", "Petugas"),
        ("auditor", "Auditor"),
        ("viewer", "Pembaca"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="koperasi_accesses",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="accesses",
        blank=True,
        null=True,
        help_text="Kosongkan untuk akses ke seluruh perusahaan.",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "company"],
                name="unique_koperasi_user_company",
                nulls_distinct=False,
            )
        ]
        verbose_name = "Hak akses Koperasi"
        verbose_name_plural = "Hak akses Koperasi"

    def __str__(self):
        scope = self.company.name if self.company else "Semua perusahaan"
        return f"{self.user.username} - {self.get_role_display()} ({scope})"


class Member(models.Model):
    STATUS_CHOICES = [
        ("active", "Aktif"),
        ("inactive", "Tidak Aktif"),
        ("resigned", "Keluar"),
    ]

    member_number = models.CharField("Nomor anggota", max_length=30, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="members"
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="koperasi_member",
        blank=True,
        null=True,
    )
    employee_number = models.CharField("NIP/NIK", max_length=50, blank=True)
    full_name = models.CharField("Nama lengkap", max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField("Alamat", blank=True)
    join_date = models.DateField("Tanggal bergabung")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active"
    )
    mandatory_saving_amount = models.DecimalField(
        "Simpanan wajib bulanan",
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["company", "status"], name="member_company_status_idx")
        ]
        verbose_name = "Anggota"
        verbose_name_plural = "Anggota"

    def __str__(self):
        return f"{self.member_number} - {self.full_name}"

    def saving_balance(self, saving_type=None):
        transactions = self.saving_transactions.all()
        if saving_type:
            transactions = transactions.filter(saving_type=saving_type)
        deposits = transactions.filter(direction="deposit").aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        withdrawals = transactions.filter(direction="withdrawal").aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        return deposits - withdrawals


class SavingTransaction(models.Model):
    TYPE_CHOICES = [
        ("principal", "Simpanan Pokok"),
        ("mandatory", "Simpanan Wajib"),
        ("voluntary", "Simpanan Sukarela"),
    ]
    DIRECTION_CHOICES = [
        ("deposit", "Setoran"),
        ("withdrawal", "Penarikan"),
    ]

    transaction_number = models.CharField(
        "Nomor transaksi", max_length=40, unique=True
    )
    member = models.ForeignKey(
        Member, on_delete=models.PROTECT, related_name="saving_transactions"
    )
    saving_type = models.CharField(
        "Jenis simpanan", max_length=20, choices=TYPE_CHOICES
    )
    direction = models.CharField(
        "Jenis transaksi", max_length=20, choices=DIRECTION_CHOICES
    )
    transaction_date = models.DateField("Tanggal")
    amount = models.DecimalField(
        "Jumlah", max_digits=15, decimal_places=2, validators=MONEY_VALIDATORS
    )
    reference = models.CharField("Referensi", max_length=100, blank=True)
    notes = models.TextField("Catatan", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_saving_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date", "-pk"]
        indexes = [
            models.Index(
                fields=["member", "transaction_date"],
                name="saving_member_date_idx",
            )
        ]
        verbose_name = "Transaksi simpanan"
        verbose_name_plural = "Transaksi simpanan"

    def __str__(self):
        return self.transaction_number


class Loan(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draf"),
        ("submitted", "Diajukan"),
        ("approved", "Disetujui"),
        ("rejected", "Ditolak"),
        ("active", "Berjalan"),
        ("paid", "Lunas"),
        ("cancelled", "Dibatalkan"),
    ]

    loan_number = models.CharField("Nomor pinjaman", max_length=40, unique=True)
    member = models.ForeignKey(
        Member, on_delete=models.PROTECT, related_name="loans"
    )
    application_date = models.DateField("Tanggal pengajuan")
    principal_amount = models.DecimalField(
        "Pokok pinjaman",
        max_digits=15,
        decimal_places=2,
        validators=MONEY_VALIDATORS,
    )
    interest_rate = models.DecimalField(
        "Bunga per tahun (%)",
        max_digits=6,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    term_months = models.PositiveIntegerField("Tenor (bulan)")
    purpose = models.TextField("Tujuan pinjaman")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="submitted"
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_koperasi_loans",
        blank=True,
        null=True,
    )
    disbursed_date = models.DateField("Tanggal pencairan", blank=True, null=True)
    notes = models.TextField("Catatan", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_koperasi_loans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-application_date", "-pk"]
        indexes = [
            models.Index(fields=["member", "status"], name="loan_member_status_idx")
        ]
        verbose_name = "Pinjaman"
        verbose_name_plural = "Pinjaman"

    def __str__(self):
        return self.loan_number

    @property
    def total_interest(self):
        return (
            self.principal_amount
            * self.interest_rate
            / Decimal("100")
            * Decimal(self.term_months)
            / Decimal("12")
        ).quantize(Decimal("0.01"))

    @property
    def total_due(self):
        return self.principal_amount + self.total_interest

    @property
    def amount_paid(self):
        return self.installments.aggregate(
            total=Sum("principal_amount") + Sum("interest_amount")
        )["total"] or Decimal("0")

    @property
    def outstanding_amount(self):
        return max(self.total_due - self.amount_paid, Decimal("0"))


class LoanInstallment(models.Model):
    loan = models.ForeignKey(
        Loan, on_delete=models.PROTECT, related_name="installments"
    )
    payment_number = models.CharField(
        "Nomor pembayaran", max_length=40, unique=True
    )
    payment_date = models.DateField("Tanggal pembayaran")
    principal_amount = models.DecimalField(
        "Angsuran pokok",
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    interest_amount = models.DecimalField(
        "Bunga",
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    penalty_amount = models.DecimalField(
        "Denda",
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    reference = models.CharField("Referensi", max_length=100, blank=True)
    notes = models.TextField("Catatan", blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="received_loan_installments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-pk"]
        verbose_name = "Angsuran pinjaman"
        verbose_name_plural = "Angsuran pinjaman"

    def __str__(self):
        return self.payment_number

    @property
    def total_amount(self):
        return self.principal_amount + self.interest_amount + self.penalty_amount


class CashTransaction(models.Model):
    TYPE_CHOICES = [
        ("income", "Pemasukan"),
        ("expense", "Pengeluaran"),
    ]

    transaction_number = models.CharField(
        "Nomor transaksi", max_length=40, unique=True
    )
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="cash_transactions"
    )
    transaction_date = models.DateField("Tanggal")
    transaction_type = models.CharField(
        "Jenis transaksi", max_length=20, choices=TYPE_CHOICES
    )
    category = models.CharField("Kategori", max_length=100)
    amount = models.DecimalField(
        "Jumlah", max_digits=15, decimal_places=2, validators=MONEY_VALIDATORS
    )
    description = models.TextField("Keterangan")
    reference = models.CharField("Referensi", max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_cash_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date", "-pk"]
        verbose_name = "Transaksi kas"
        verbose_name_plural = "Transaksi kas"

    def __str__(self):
        return self.transaction_number
