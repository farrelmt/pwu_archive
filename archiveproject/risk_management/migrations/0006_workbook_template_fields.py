import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("risk_management", "0005_remove_default_viewer_access"),
    ]

    operations = [
        migrations.AddField(model_name="riskregister", name="strategic_objective", field=models.TextField(blank=True, verbose_name="Sasaran terkait")),
        migrations.AddField(model_name="riskregister", name="indication", field=models.TextField(blank=True, verbose_name="Indikasi risiko")),
        migrations.AddField(model_name="riskregister", name="controllability", field=models.CharField(blank=True, choices=[("", "-"), ("controllable", "Controllable"), ("uncontrollable", "Uncontrollable")], max_length=20, verbose_name="Kendali penyebab")),
        migrations.AddField(model_name="riskregister", name="control_effectiveness", field=models.CharField(blank=True, choices=[("", "-"), ("ineffective", "Tidak Efektif"), ("adequate", "Cukup Efektif"), ("effective", "Efektif")], max_length=20, verbose_name="Efektivitas pengendalian")),
        migrations.AddField(model_name="riskregister", name="is_priority", field=models.BooleanField(default=False, verbose_name="Nominasi prioritas risiko")),
        migrations.AddField(model_name="riskregister", name="risk_officer", field=models.CharField(blank=True, max_length=160, verbose_name="Risk officer")),
        migrations.AddField(model_name="riskmonitoring", name="expected_likelihood", field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name="Kemungkinan yang diharapkan")),
        migrations.AddField(model_name="riskmonitoring", name="expected_impact", field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name="Dampak yang diharapkan")),
        migrations.CreateModel(
            name="RiskTreatment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("option", models.TextField(blank=True, verbose_name="Opsi perlakuan risiko")),
                ("action_plan", models.TextField(verbose_name="Rencana aksi perlakuan risiko")),
                ("expected_likelihood", models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name="Kemungkinan yang diharapkan")),
                ("expected_impact", models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name="Dampak yang diharapkan")),
                ("target_date", models.DateField(blank=True, null=True, verbose_name="Jadwal pelaksanaan")),
                ("responsible_person", models.CharField(blank=True, max_length=160, verbose_name="Penanggung jawab")),
                ("notes", models.TextField(blank=True, verbose_name="Keterangan")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_risk_treatments", to=settings.AUTH_USER_MODEL)),
                ("risk", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="treatments", to="risk_management.riskregister")),
                ("updated_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="updated_risk_treatments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Perlakuan risiko", "verbose_name_plural": "Perlakuan risiko", "ordering": ["target_date", "pk"]},
        ),
    ]
