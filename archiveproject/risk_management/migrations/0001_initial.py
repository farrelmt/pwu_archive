import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations, models


DIVISIONS = [
    ("AKT", "Akuntansi"),
    ("KEU", "Keuangan"),
    ("MRI", "Manajemen Risiko"),
    ("LUM", "Legal dan Umum"),
    ("AST", "Aset"),
    ("SPI", "Satuan Pengawasan Internal"),
    ("SDM", "Sumber Daya Manusia"),
    ("OPS", "Operasional"),
    ("TI", "Teknologi Informasi"),
]


def seed_risk_users(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    Division = apps.get_model("risk_management", "RiskDivision")
    Access = apps.get_model("risk_management", "RiskAccess")

    divisions = []
    for code, name in DIVISIONS:
        division, _ = Division.objects.update_or_create(code=code, defaults={"name": name, "is_active": True})
        divisions.append(division)

    global_users = [
        ("risk_head_manager", "Kepala", "Manajemen Risiko", "head_manager"),
        ("risk_manager_member", "Anggota", "Manajemen Risiko", "manager_member"),
    ]
    for username, first_name, last_name, role in global_users:
        user, _ = User.objects.get_or_create(username=username, defaults={"role": "risk", "email": "it.pwujatim@gmail.com"})
        user.role = "risk"
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.password = make_password(username)
        user.save()
        Access.objects.update_or_create(user=user, defaults={"role": role, "division": None, "is_active": True})

    for number, division in enumerate(divisions, start=1):
        officer_username = f"risk_officer_{number}"
        officer, _ = User.objects.get_or_create(username=officer_username, defaults={"role": "risk", "email": "it.pwujatim@gmail.com"})
        officer.role = "risk"
        officer.first_name = "Risk Officer"
        officer.last_name = division.name
        officer.is_active = True
        officer.password = make_password(officer_username)
        officer.save()
        Access.objects.update_or_create(user=officer, defaults={"role": "risk_officer", "division": division, "is_active": True})

        head_username = f"risk_head_division_{number}"
        head, _ = User.objects.get_or_create(username=head_username, defaults={"role": "risk", "email": "it.pwujatim@gmail.com"})
        head.role = "risk"
        head.first_name = "Kepala Divisi"
        head.last_name = division.name
        head.is_active = True
        head.password = make_password(head_username)
        head.save()
        Access.objects.update_or_create(user=head, defaults={"role": "division_head", "division": division, "is_active": True})


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("accounts", "0011_add_risk_user_role")]
    operations = [
        migrations.CreateModel(
            name="RiskDivision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=20, unique=True, verbose_name="Kode")),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="Nama divisi")),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"verbose_name": "Divisi risiko", "verbose_name_plural": "Divisi risiko", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="RiskAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("head_manager", "Kepala Manajemen Risiko"), ("manager_member", "Anggota Manajemen Risiko"), ("risk_officer", "Risk Officer"), ("division_head", "Kepala Divisi")], max_length=30)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("division", models.ForeignKey(blank=True, help_text="Wajib untuk Risk Officer dan Kepala Divisi.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="accesses", to="risk_management.riskdivision")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="risk_access", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Hak akses risiko", "verbose_name_plural": "Hak akses risiko"},
        ),
        migrations.CreateModel(
            name="RiskRegister",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("risk_code", models.CharField(editable=False, max_length=30, unique=True, verbose_name="Kode risiko")),
                ("title", models.CharField(max_length=220, verbose_name="Risiko")),
                ("category", models.CharField(choices=[("strategic", "Strategis"), ("operational", "Operasional"), ("financial", "Keuangan"), ("compliance", "Kepatuhan"), ("reputation", "Reputasi"), ("technology", "Teknologi")], max_length=20, verbose_name="Kategori")),
                ("description", models.TextField(verbose_name="Uraian risiko")),
                ("cause", models.TextField(verbose_name="Penyebab")),
                ("impact", models.TextField(verbose_name="Dampak")),
                ("inherent_likelihood", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name="Kemungkinan inheren")),
                ("inherent_impact", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name="Dampak inheren")),
                ("existing_controls", models.TextField(blank=True, verbose_name="Pengendalian yang ada")),
                ("mitigation_plan", models.TextField(blank=True, verbose_name="Rencana mitigasi")),
                ("risk_owner", models.CharField(max_length=160, verbose_name="Pemilik risiko")),
                ("target_date", models.DateField(blank=True, null=True, verbose_name="Target penyelesaian")),
                ("residual_likelihood", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name="Kemungkinan residual")),
                ("residual_impact", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name="Dampak residual")),
                ("status", models.CharField(choices=[("open", "Teridentifikasi"), ("mitigating", "Dalam Mitigasi"), ("monitoring", "Pemantauan"), ("closed", "Selesai")], default="open", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_risks", to=settings.AUTH_USER_MODEL)),
                ("division", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="risks", to="risk_management.riskdivision")),
                ("updated_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="updated_risks", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at", "risk_code"]},
        ),
        migrations.CreateModel(
            name="RiskActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=40)),
                ("description", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("risk", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activities", to="risk_management.riskregister")),
            ],
            options={"verbose_name_plural": "Aktivitas risiko", "ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="riskregister", index=models.Index(fields=["division", "status"], name="risk_division_status_idx")),
        migrations.AddIndex(model_name="riskregister", index=models.Index(fields=["category", "status"], name="risk_category_status_idx")),
        migrations.RunPython(seed_risk_users, migrations.RunPython.noop),
    ]
