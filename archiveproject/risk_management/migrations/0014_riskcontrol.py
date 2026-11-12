from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0013_risk_register_sop_codes")]

    operations = [
        migrations.CreateModel(
            name="RiskControl",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveSmallIntegerField()),
                ("description", models.TextField(verbose_name="Pengendalian yang ada")),
                ("effectiveness", models.CharField(blank=True, choices=[("", "-"), ("ineffective", "Tidak Efektif"), ("adequate", "Cukup Efektif"), ("effective", "Efektif")], max_length=20, verbose_name="Efektivitas pengendalian")),
                ("notes", models.TextField(blank=True, verbose_name="Keterangan")),
                ("risk", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="additional_controls", to="risk_management.riskregister")),
            ],
            options={"ordering": ["position", "pk"]},
        ),
        migrations.AddConstraint(
            model_name="riskcontrol",
            constraint=models.UniqueConstraint(fields=("risk", "position"), name="unique_risk_control_position"),
        ),
    ]
