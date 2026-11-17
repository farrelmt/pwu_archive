from django.db import migrations


def use_division_in_strategic_codes(apps, schema_editor):
    Risk = apps.get_model("risk_management", "RiskRegister")
    Sequence = apps.get_model("risk_management", "RiskCodeSequence")
    database = schema_editor.connection.alias

    last_numbers = {}
    for code in Risk.objects.using(database).values_list("risk_code", flat=True):
        prefix, separator, number = code.rpartition("/")
        if separator and number.isdigit():
            last_numbers[prefix] = max(last_numbers.get(prefix, 0), int(number))
    for sequence in Sequence.objects.using(database).all():
        last_numbers[sequence.prefix] = max(
            last_numbers.get(sequence.prefix, 0), sequence.last_number,
        )

    strategic_risks = Risk.objects.using(database).filter(risk_kind="A").select_related(
        "division"
    ).order_by("created_at", "pk")
    for risk in strategic_risks:
        prefix = f"A/{risk.division.code}/{risk.code_category}"
        if risk.risk_code.startswith(f"{prefix}/"):
            continue
        last_numbers[prefix] = last_numbers.get(prefix, 0) + 1
        Risk.objects.using(database).filter(pk=risk.pk).update(
            risk_code=f"{prefix}/{last_numbers[prefix]:03d}"
        )

    for prefix, last_number in last_numbers.items():
        Sequence.objects.using(database).update_or_create(
            prefix=prefix, defaults={"last_number": last_number},
        )


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0014_riskcontrol")]

    operations = [
        migrations.RunPython(use_division_in_strategic_codes, migrations.RunPython.noop),
    ]
