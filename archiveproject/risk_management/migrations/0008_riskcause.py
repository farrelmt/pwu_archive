from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0007_risk_document_notes")]

    operations = [
        migrations.CreateModel(
            name="RiskCause",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveSmallIntegerField()),
                ("description", models.TextField(verbose_name="Sebab risiko")),
                ("controllability", models.CharField(blank=True, choices=[("", "-"), ("controllable", "Controllable"), ("uncontrollable", "Uncontrollable")], max_length=20, verbose_name="Kendali penyebab")),
                ("risk", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="additional_causes", to="risk_management.riskregister")),
            ],
            options={"ordering": ["position", "pk"]},
        ),
        migrations.AddConstraint(
            model_name="riskcause",
            constraint=models.UniqueConstraint(fields=("risk", "position"), name="unique_risk_cause_position"),
        ),
    ]
