from django.db import migrations, models


def assign_sop_codes(apps, schema_editor):
    Division = apps.get_model("risk_management", "RiskDivision")
    Risk = apps.get_model("risk_management", "RiskRegister")
    Sequence = apps.get_model("risk_management", "RiskCodeSequence")
    Division.objects.get_or_create(
        code="SPR", defaults={"name": "Sekretaris Perusahaan", "is_active": True},
    )
    categories = {
        "financial": "001", "compliance": "004", "reputation": "005",
        "strategic": "006", "operational": "010", "technology": "010",
    }
    for risk in Risk.objects.select_related("division").order_by("created_at", "pk"):
        kind = "A" if risk.category == "strategic" else "C" if risk.division.code == "KSO" else "B"
        source = "01" if kind == "A" else ""
        category = categories.get(risk.category, "010")
        prefix = f"{kind}/{'01' if kind == 'A' else 'KSO' if kind == 'C' else risk.division.code}/{category}"
        sequence, _ = Sequence.objects.get_or_create(prefix=prefix)
        sequence.last_number += 1
        sequence.save(update_fields=["last_number"])
        Risk.objects.filter(pk=risk.pk).update(
            risk_kind=kind, risk_source=source, code_category=category,
            risk_code=f"{prefix}/{sequence.last_number:03d}",
        )


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0012_division_kso")]

    operations = [
        migrations.CreateModel(
            name="RiskCodeSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("prefix", models.CharField(max_length=32, unique=True)),
                ("last_number", models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.AddField(
            model_name="riskregister", name="risk_kind",
            field=models.CharField(choices=[("A", "A - Strategis"), ("B", "B - Operasional"), ("C", "C - Proyek")], default="B", max_length=1, verbose_name="Jenis risiko"),
        ),
        migrations.AddField(
            model_name="riskregister", name="risk_source",
            field=models.CharField(blank=True, choices=[("01", "01 - Divisi, proyek, atau kombinasi keduanya"), ("02", "02 - Selain divisi atau proyek")], max_length=2, verbose_name="Sumber risiko strategis"),
        ),
        migrations.AddField(
            model_name="riskregister", name="code_category",
            field=models.CharField(choices=[("001", "001 - Keuangan"), ("002", "002 - Fraud/Korupsi"), ("003", "003 - Legal/Hukum"), ("004", "004 - Kepatuhan"), ("005", "005 - Reputasi"), ("006", "006 - Kebijakan"), ("007", "007 - SDM"), ("008", "008 - Keselamatan Kerja"), ("009", "009 - Aset"), ("010", "010 - Kinerja")], default="010", max_length=3, verbose_name="Kategori risiko"),
        ),
        migrations.AlterField(
            model_name="riskregister", name="risk_code",
            field=models.CharField(editable=False, max_length=40, unique=True, verbose_name="Kode risiko"),
        ),
        migrations.RunPython(assign_sop_codes, migrations.RunPython.noop),
    ]
