from collections import defaultdict

from django.db import migrations


def compact_existing_codes(apps, schema_editor):
    Risk = apps.get_model("risk_management", "RiskRegister")
    Sequence = apps.get_model("risk_management", "RiskCodeSequence")
    database = schema_editor.connection.alias

    groups = defaultdict(list)
    for pk, code in Risk.objects.using(database).values_list("pk", "risk_code"):
        prefix, separator, suffix = code.rpartition("/")
        if separator and suffix.isdigit():
            groups[prefix].append((int(suffix), pk, code))

    for prefix, rows in groups.items():
        rows.sort()
        for number, (_, pk, old_code) in enumerate(rows, 1):
            new_code = f"{prefix}/{number:03d}"
            if new_code != old_code:
                Risk.objects.using(database).filter(pk=pk).update(risk_code=new_code)

    for sequence in Sequence.objects.using(database).all():
        count = len(groups.pop(sequence.prefix, []))
        if sequence.last_number != count:
            sequence.last_number = count
            sequence.save(using=database, update_fields=["last_number"])
    for prefix, rows in groups.items():
        Sequence.objects.using(database).create(prefix=prefix, last_number=len(rows))


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0015_strategic_division_codes")]

    operations = [
        migrations.RunPython(compact_existing_codes, migrations.RunPython.noop),
    ]
