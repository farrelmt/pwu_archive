from collections import defaultdict

from django.db import migrations


def number_risks_across_categories(apps, schema_editor):
    Risk = apps.get_model("risk_management", "RiskRegister")
    Sequence = apps.get_model("risk_management", "RiskCodeSequence")
    database = schema_editor.connection.alias

    groups = defaultdict(list)
    for risk in Risk.objects.using(database).select_related("division").order_by("created_at", "pk"):
        source = "KSO" if risk.risk_kind == "C" else risk.division.code
        group = f"{risk.risk_kind}/{source}"
        groups[group].append((risk.pk, f"{group}/{risk.code_category}"))

    # Move every code out of the way before assigning new numbers so unique
    # values from different old category series cannot collide midway through.
    for rows in groups.values():
        for pk, _ in rows:
            Risk.objects.using(database).filter(pk=pk).update(risk_code=f"TMP-RISK-{pk}")
    for rows in groups.values():
        for number, (pk, prefix) in enumerate(rows, 1):
            Risk.objects.using(database).filter(pk=pk).update(
                risk_code=f"{prefix}/{number:03d}"
            )

    Sequence.objects.using(database).all().delete()
    Sequence.objects.using(database).bulk_create([
        Sequence(prefix=group, last_number=len(rows))
        for group, rows in groups.items()
    ])


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0016_compact_risk_code_sequences")]

    operations = [
        migrations.RunPython(number_risks_across_categories, migrations.RunPython.noop),
    ]
