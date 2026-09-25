import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class RiskDivision(models.Model):
    code = models.CharField("Kode", max_length=20, unique=True)
    name = models.CharField("Nama divisi", max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Divisi risiko"
        verbose_name_plural = "Divisi risiko"

    def __str__(self):
        return self.name


class RiskAccess(models.Model):
    ROLE_CHOICES = [
        ("head_manager", "Kepala Manajemen Risiko"),
        ("manager_member", "Anggota Manajemen Risiko"),
        ("risk_officer", "Risk Officer"),
        ("division_head", "Kepala Divisi"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="risk_accesses",
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    division = models.ForeignKey(
        RiskDivision,
        on_delete=models.PROTECT,
        related_name="accesses",
        blank=True,
        null=True,
        help_text="Wajib untuk Risk Officer dan Kepala Divisi.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "division"],
                name="unique_risk_user_role_division",
                nulls_distinct=False,
            )
        ]
        verbose_name = "Hak akses risiko"
        verbose_name_plural = "Hak akses risiko"

    def __str__(self):
        scope = self.division.name if self.division else "Semua divisi"
        return f"{self.user.username} - {self.get_role_display()} ({scope})"


class RiskRegister(models.Model):
    CATEGORY_CHOICES = [
        ("strategic", "Strategis"),
        ("operational", "Operasional"),
        ("financial", "Keuangan"),
        ("compliance", "Kepatuhan"),
        ("reputation", "Reputasi"),
        ("technology", "Teknologi"),
    ]
    STATUS_CHOICES = [
        ("open", "Teridentifikasi"),
        ("mitigating", "Dalam Mitigasi"),
        ("monitoring", "Pemantauan"),
        ("closed", "Selesai"),
    ]

    risk_code = models.CharField("Kode risiko", max_length=30, unique=True, editable=False)
    division = models.ForeignKey(RiskDivision, on_delete=models.PROTECT, related_name="risks")
    title = models.CharField("Risiko", max_length=220)
    category = models.CharField("Kategori", max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField("Uraian risiko")
    cause = models.TextField("Penyebab")
    impact = models.TextField("Dampak")
    inherent_likelihood = models.PositiveSmallIntegerField(
        "Kemungkinan inheren", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    inherent_impact = models.PositiveSmallIntegerField(
        "Dampak inheren", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    existing_controls = models.TextField("Pengendalian yang ada", blank=True)
    mitigation_plan = models.TextField("Rencana mitigasi", blank=True)
    risk_owner = models.CharField("Pemilik risiko", max_length=160)
    target_date = models.DateField("Target penyelesaian", blank=True, null=True)
    residual_likelihood = models.PositiveSmallIntegerField(
        "Kemungkinan residual", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    residual_impact = models.PositiveSmallIntegerField(
        "Dampak residual", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_risks"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="updated_risks"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "risk_code"]
        indexes = [
            models.Index(fields=["division", "status"], name="risk_division_status_idx"),
            models.Index(fields=["category", "status"], name="risk_category_status_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.risk_code:
            self.risk_code = f"RSK-{timezone.localdate():%Y}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    @property
    def inherent_score(self):
        return self.inherent_likelihood * self.inherent_impact

    @property
    def residual_score(self):
        return self.residual_likelihood * self.residual_impact

    @staticmethod
    def level_for(score):
        if score >= 20:
            return "Sangat Tinggi"
        if score >= 12:
            return "Tinggi"
        if score >= 5:
            return "Sedang"
        return "Rendah"

    @property
    def risk_level(self):
        return self.level_for(self.residual_score)

    def __str__(self):
        return f"{self.risk_code} - {self.title}"


class RiskActivity(models.Model):
    risk = models.ForeignKey(RiskRegister, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=40)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Aktivitas risiko"


class RiskMonitoring(models.Model):
    QUARTER_CHOICES = [
        (1, "Triwulan I"),
        (2, "Triwulan II"),
        (3, "Triwulan III"),
        (4, "Triwulan IV"),
    ]

    risk = models.ForeignKey(
        RiskRegister, on_delete=models.CASCADE, related_name="monitorings"
    )
    year = models.PositiveSmallIntegerField("Tahun")
    quarter = models.PositiveSmallIntegerField("Triwulan", choices=QUARTER_CHOICES)
    initial_likelihood = models.PositiveSmallIntegerField(
        "Kemungkinan awal", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    initial_impact = models.PositiveSmallIntegerField(
        "Dampak awal", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    final_likelihood = models.PositiveSmallIntegerField(
        "Kemungkinan akhir", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    final_impact = models.PositiveSmallIntegerField(
        "Dampak akhir", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    business_environment_changes = models.TextField(
        "Perubahan lingkungan bisnis", blank=True
    )
    evaluation_notes = models.TextField("Catatan evaluasi", blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_risk_monitorings",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-quarter", "risk__risk_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["risk", "year", "quarter"],
                name="risk_monitoring_period_unique",
            )
        ]
        indexes = [
            models.Index(fields=["year", "quarter"], name="risk_monitor_period_idx")
        ]
        verbose_name = "Pemantauan risiko"
        verbose_name_plural = "Pemantauan risiko"

    @property
    def initial_score(self):
        return self.initial_likelihood * self.initial_impact

    @property
    def final_score(self):
        return self.final_likelihood * self.final_impact

    @property
    def score_reduction(self):
        return self.initial_score - self.final_score

    @property
    def final_level(self):
        return RiskRegister.level_for(self.final_score)

    def __str__(self):
        return f"{self.risk.risk_code} - {self.get_quarter_display()} {self.year}"


class RiskActionPlan(models.Model):
    STATUS_CHOICES = [
        ("planned", "Direncanakan"),
        ("in_progress", "Dalam Proses"),
        ("completed", "Terealisasi"),
        ("delayed", "Terlambat"),
        ("cancelled", "Dibatalkan"),
    ]

    monitoring = models.ForeignKey(
        RiskMonitoring, on_delete=models.CASCADE, related_name="action_plans"
    )
    description = models.TextField("Rencana aksi")
    responsible_person = models.CharField("Penanggung jawab", max_length=160)
    target_date = models.DateField("Target penyelesaian", blank=True, null=True)
    realization = models.TextField("Realisasi", blank=True)
    realization_date = models.DateField("Tanggal realisasi", blank=True, null=True)
    progress = models.PositiveSmallIntegerField(
        "Progres (%)", default=0, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_risk_action_plans",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_risk_action_plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["target_date", "pk"]
        indexes = [models.Index(fields=["status", "target_date"], name="risk_action_status_idx")]
        verbose_name = "Rencana aksi risiko"
        verbose_name_plural = "Rencana aksi risiko"

    @property
    def is_realized(self):
        return self.status == "completed"

    def __str__(self):
        return f"{self.monitoring}: {self.description[:60]}"
