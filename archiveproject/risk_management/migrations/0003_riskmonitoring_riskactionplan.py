import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("risk_management", "0002_add_viewer_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="RiskMonitoring",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveSmallIntegerField(verbose_name="Tahun")),
                ("quarter", models.PositiveSmallIntegerField(choices=[(1, "Triwulan I"), (2, "Triwulan II"), (3, "Triwulan III"), (4, "Triwulan IV")], verbose_name="Triwulan")),
                ("initial_likelihood", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name="Kemungkinan awal")),
                ("initial_impact", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name="Dampak awal")),
                ("final_likelihood", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name="Kemungkinan akhir")),
                ("final_impact", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name="Dampak akhir")),
                ("business_environment_changes", models.TextField(blank=True, verbose_name="Perubahan lingkungan bisnis")),
                ("evaluation_notes", models.TextField(blank=True, verbose_name="Catatan evaluasi")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("risk", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="monitorings", to="risk_management.riskregister")),
                ("updated_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="updated_risk_monitorings", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Pemantauan risiko",
                "verbose_name_plural": "Pemantauan risiko",
                "ordering": ["-year", "-quarter", "risk__risk_code"],
            },
        ),
        migrations.CreateModel(
            name="RiskActionPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.TextField(verbose_name="Rencana aksi")),
                ("responsible_person", models.CharField(max_length=160, verbose_name="Penanggung jawab")),
                ("target_date", models.DateField(blank=True, null=True, verbose_name="Target penyelesaian")),
                ("realization", models.TextField(blank=True, verbose_name="Realisasi")),
                ("realization_date", models.DateField(blank=True, null=True, verbose_name="Tanggal realisasi")),
                ("progress", models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name="Progres (%)")),
                ("status", models.CharField(choices=[("planned", "Direncanakan"), ("in_progress", "Dalam Proses"), ("completed", "Terealisasi"), ("delayed", "Terlambat"), ("cancelled", "Dibatalkan")], default="planned", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_risk_action_plans", to=settings.AUTH_USER_MODEL)),
                ("monitoring", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="action_plans", to="risk_management.riskmonitoring")),
                ("updated_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="updated_risk_action_plans", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Rencana aksi risiko",
                "verbose_name_plural": "Rencana aksi risiko",
                "ordering": ["target_date", "pk"],
            },
        ),
        migrations.AddConstraint(
            model_name="riskmonitoring",
            constraint=models.UniqueConstraint(fields=("risk", "year", "quarter"), name="risk_monitoring_period_unique"),
        ),
        migrations.AddIndex(
            model_name="riskmonitoring",
            index=models.Index(fields=["year", "quarter"], name="risk_monitor_period_idx"),
        ),
        migrations.AddIndex(
            model_name="riskactionplan",
            index=models.Index(fields=["status", "target_date"], name="risk_action_status_idx"),
        ),
    ]
