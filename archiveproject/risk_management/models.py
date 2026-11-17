from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import DEFAULT_DB_ALIAS, models, transaction

from .scoring import level_for


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


class RiskCodeSequence(models.Model):
    prefix = models.CharField(max_length=32, unique=True)
    last_number = models.PositiveIntegerField(default=0)


def compact_risk_codes(group, *, sequence, using):
    """Close gaps across categories within one risk type and division."""
    rows = list(RiskRegister.objects.using(using).filter(
        risk_code__startswith=f"{group}/"
    ).values_list("pk", "risk_code"))
    rows.sort(key=lambda row: (int(row[1].rpartition("/")[2]), row[0]))
    for number, (pk, old_code) in enumerate(rows, 1):
        full_prefix = old_code.rpartition("/")[0]
        new_code = f"{full_prefix}/{number:03d}"
        if old_code != new_code:
            RiskRegister.objects.using(using).filter(pk=pk).update(risk_code=new_code)
    if sequence.last_number != len(rows):
        sequence.last_number = len(rows)
        sequence.save(using=using, update_fields=["last_number"])


class RiskAccess(models.Model):
    ROLE_CHOICES = [
        ("head_manager", "Kepala Manajemen Risiko"),
        ("manager_member", "Anggota Manajemen Risiko"),
        ("risk_officer", "Risk Officer"),
        ("division_head", "Kepala Divisi"),
        ("staff_it", "Staff IT"),
        ("staff_hrd", "HRD"),
        ("staff_humas", "Humas"),
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
    RISK_KIND_CHOICES = [
        ("A", "A - Strategis"), ("B", "B - Operasional"), ("C", "C - Proyek"),
    ]
    SOURCE_CHOICES = [
        ("01", "01 - Divisi, proyek, atau kombinasi keduanya"),
        ("02", "02 - Selain divisi atau proyek"),
    ]
    CODE_CATEGORY_CHOICES = [
        ("001", "001 - Keuangan"), ("002", "002 - Fraud/Korupsi"),
        ("003", "003 - Legal/Hukum"), ("004", "004 - Kepatuhan"),
        ("005", "005 - Reputasi"), ("006", "006 - Kebijakan"),
        ("007", "007 - SDM"), ("008", "008 - Keselamatan Kerja"),
        ("009", "009 - Aset"), ("010", "010 - Kinerja"),
    ]
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
    CONTROLLABILITY_CHOICES = [
        ("", "-"),
        ("controllable", "Controllable"),
        ("uncontrollable", "Uncontrollable"),
    ]
    CONTROL_EFFECTIVENESS_CHOICES = [
        ("", "-"),
        ("ineffective", "Tidak Efektif"),
        ("adequate", "Cukup Efektif"),
        ("effective", "Efektif"),
    ]

    risk_code = models.CharField("Kode risiko", max_length=40, unique=True, editable=False)
    division = models.ForeignKey(RiskDivision, on_delete=models.PROTECT, related_name="risks")
    risk_kind = models.CharField("Jenis risiko", max_length=1, choices=RISK_KIND_CHOICES, default="B")
    risk_source = models.CharField("Sumber risiko strategis", max_length=2, choices=SOURCE_CHOICES, blank=True)
    code_category = models.CharField("Kategori risiko", max_length=3, choices=CODE_CATEGORY_CHOICES, default="010")
    title = models.CharField("Risiko", max_length=220)
    category = models.CharField("Kategori", max_length=20, choices=CATEGORY_CHOICES)
    strategic_objective = models.TextField("Sasaran terkait", blank=True)
    description = models.TextField("Uraian risiko")
    indication = models.TextField("Indikasi risiko", blank=True)
    cause = models.TextField("Penyebab")
    controllability = models.CharField(
        "Kendali penyebab", max_length=20, choices=CONTROLLABILITY_CHOICES, blank=True
    )
    impact = models.TextField("Dampak")
    inherent_likelihood = models.PositiveSmallIntegerField(
        "Kemungkinan inheren", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    inherent_impact = models.PositiveSmallIntegerField(
        "Dampak inheren", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    existing_controls = models.TextField("Pengendalian yang ada", blank=True)
    control_effectiveness = models.CharField(
        "Efektivitas pengendalian",
        max_length=20,
        choices=CONTROL_EFFECTIVENESS_CHOICES,
        blank=True,
    )
    is_priority = models.BooleanField("Nominasi prioritas risiko", default=False)
    identification_notes = models.TextField("Keterangan identifikasi", blank=True)
    evaluation_notes = models.TextField("Keterangan analisis dan evaluasi", blank=True)
    mitigation_plan = models.TextField("Rencana mitigasi", blank=True)
    risk_owner = models.CharField("Pemilik risiko", max_length=160)
    risk_officer = models.CharField("Risk officer", max_length=160, blank=True)
    target_date = models.DateField("Target penyelesaian", blank=True, null=True)
    residual_likelihood = models.PositiveSmallIntegerField(
        "Kemungkinan residual", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    residual_impact = models.PositiveSmallIntegerField(
        "Dampak residual", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
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
        prefix = self.code_prefix()
        group = prefix.rpartition("/")[0]
        using = kwargs.get("using") or self._state.db or DEFAULT_DB_ALIAS
        previous_code = (
            RiskRegister.objects.using(using).filter(pk=self.pk).values_list("risk_code", flat=True).first()
            if self.pk else None
        )
        previous_group = previous_code.rpartition("/")[0].rpartition("/")[0] if previous_code else None
        with transaction.atomic(using=using):
            sequences = {}
            for series in sorted({group, previous_group} - {None}):
                sequences[series], _ = RiskCodeSequence.objects.using(using).select_for_update().get_or_create(
                    prefix=series
                )
            if previous_code and previous_group == group:
                new_code = f"{prefix}/{previous_code.rpartition('/')[2]}"
            else:
                sequence = sequences[group]
                sequence.last_number += 1
                sequence.save(using=using, update_fields=["last_number"])
                new_code = f"{prefix}/{sequence.last_number:03d}"
            if self.risk_code != new_code:
                self.risk_code = new_code
                if kwargs.get("update_fields") is not None:
                    kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                        "risk_code", "risk_kind", "risk_source", "code_category", "division",
                    }
            super().save(*args, **kwargs)
            if previous_group and previous_group != group:
                compact_risk_codes(previous_group, sequence=sequences[previous_group], using=using)

    def delete(self, *args, **kwargs):
        using = kwargs.get("using") or self._state.db or DEFAULT_DB_ALIAS
        with transaction.atomic(using=using):
            code = RiskRegister.objects.using(using).filter(pk=self.pk).values_list("risk_code", flat=True).first()
            if code is None:
                return super().delete(*args, **kwargs)
            group = code.rpartition("/")[0].rpartition("/")[0]
            sequence, _ = RiskCodeSequence.objects.using(using).select_for_update().get_or_create(prefix=group)
            result = super().delete(*args, **kwargs)
            compact_risk_codes(group, sequence=sequence, using=using)
            return result

    def code_prefix(self):
        if self.risk_kind == "C":
            source = "KSO"
        else:
            source = self.division.code
        return f"{self.risk_kind}/{source}/{self.code_category}"

    @property
    def inherent_score(self):
        if self.inherent_likelihood is None or self.inherent_impact is None:
            return None
        return self.inherent_likelihood * self.inherent_impact

    @property
    def residual_score(self):
        if self.residual_likelihood is None or self.residual_impact is None:
            return None
        return self.residual_likelihood * self.residual_impact

    level_for = staticmethod(level_for)

    @property
    def inherent_level(self):
        return self.level_for(self.inherent_likelihood, self.inherent_impact) if self.inherent_score is not None else "-"

    @property
    def risk_level(self):
        return self.level_for(self.residual_likelihood, self.residual_impact) if self.residual_score is not None else "-"

    def __str__(self):
        return f"{self.risk_code} - {self.title}"


class RiskCause(models.Model):
    risk = models.ForeignKey(RiskRegister, on_delete=models.CASCADE, related_name="additional_causes")
    position = models.PositiveSmallIntegerField()
    description = models.TextField("Sebab risiko")
    controllability = models.CharField(
        "Kendali penyebab", max_length=20,
        choices=RiskRegister.CONTROLLABILITY_CHOICES, blank=True,
    )
    impact = models.TextField("Dampak", blank=True)
    inherent_likelihood = models.PositiveSmallIntegerField(
        "Kemungkinan inheren", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    inherent_impact = models.PositiveSmallIntegerField(
        "Dampak inheren", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    identification_notes = models.TextField("Keterangan identifikasi", blank=True)

    @property
    def inherent_level(self):
        if self.inherent_likelihood and self.inherent_impact:
            return RiskRegister.level_for(self.inherent_likelihood, self.inherent_impact)
        return "-"

    class Meta:
        ordering = ["position", "pk"]
        constraints = [models.UniqueConstraint(fields=["risk", "position"], name="unique_risk_cause_position")]


class RiskControl(models.Model):
    risk = models.ForeignKey(RiskRegister, on_delete=models.CASCADE, related_name="additional_controls")
    position = models.PositiveSmallIntegerField()
    description = models.TextField("Pengendalian yang ada")
    effectiveness = models.CharField(
        "Efektivitas pengendalian", max_length=20,
        choices=RiskRegister.CONTROL_EFFECTIVENESS_CHOICES, blank=True,
    )
    notes = models.TextField("Keterangan", blank=True)

    class Meta:
        ordering = ["position", "pk"]
        constraints = [models.UniqueConstraint(fields=["risk", "position"], name="unique_risk_control_position")]


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
    expected_likelihood = models.PositiveSmallIntegerField(
        "Kemungkinan yang diharapkan",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        blank=True,
        null=True,
    )
    expected_impact = models.PositiveSmallIntegerField(
        "Dampak yang diharapkan",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        blank=True,
        null=True,
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
        return RiskRegister.level_for(self.final_likelihood, self.final_impact)

    @property
    def initial_level(self):
        return RiskRegister.level_for(self.initial_likelihood, self.initial_impact)

    @property
    def expected_level(self):
        if self.expected_score is None:
            return None
        return RiskRegister.level_for(self.expected_likelihood, self.expected_impact)

    @property
    def expected_score(self):
        if self.expected_likelihood is None or self.expected_impact is None:
            return None
        return self.expected_likelihood * self.expected_impact

    @property
    def deviation(self):
        if self.expected_score is None:
            return None
        return self.expected_score - self.final_score

    def __str__(self):
        return f"{self.risk.risk_code} - {self.get_quarter_display()} {self.year}"


class RiskTreatment(models.Model):
    risk = models.ForeignKey(
        RiskRegister, on_delete=models.CASCADE, related_name="treatments"
    )
    option = models.TextField("Opsi perlakuan risiko", blank=True)
    action_plan = models.TextField("Rencana aksi perlakuan risiko")
    expected_likelihood = models.PositiveSmallIntegerField(
        "Kemungkinan yang diharapkan",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        blank=True,
        null=True,
    )
    expected_impact = models.PositiveSmallIntegerField(
        "Dampak yang diharapkan",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        blank=True,
        null=True,
    )
    target_date = models.DateField("Jadwal pelaksanaan", blank=True, null=True)
    responsible_person = models.CharField("Penanggung jawab", max_length=160, blank=True)
    notes = models.TextField("Keterangan", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_risk_treatments",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_risk_treatments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["target_date", "pk"]
        verbose_name = "Perlakuan risiko"
        verbose_name_plural = "Perlakuan risiko"

    @property
    def expected_score(self):
        if self.expected_likelihood is None or self.expected_impact is None:
            return None
        return self.expected_likelihood * self.expected_impact

    @property
    def expected_level(self):
        return RiskRegister.level_for(self.expected_likelihood, self.expected_impact) if self.expected_score else "-"

    def __str__(self):
        return f"{self.risk.risk_code}: {self.action_plan[:60]}"

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or self._state.db or DEFAULT_DB_ALIAS
        previous_plan = (
            RiskTreatment.objects.using(using).filter(pk=self.pk).values_list("action_plan", flat=True).first()
            if self.pk else None
        )
        with transaction.atomic(using=using):
            super().save(*args, **kwargs)
            if (previous_plan is not None and previous_plan != self.action_plan
                    and (kwargs.get("update_fields") is None or "action_plan" in kwargs["update_fields"])):
                RiskActionPlan.objects.using(using).filter(treatment_id=self.pk).update(
                    description=self.action_plan
                )


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
    treatment = models.ForeignKey(
        RiskTreatment, on_delete=models.SET_NULL, related_name="monitoring_actions",
        blank=True, null=True,
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
