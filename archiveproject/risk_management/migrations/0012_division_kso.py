from django.db import migrations


def update_divisions(apps, schema_editor):
    Division = apps.get_model("risk_management", "RiskDivision")
    Division.objects.filter(code__in=("OPS", "SDM", "TI")).update(is_active=False)
    Division.objects.update_or_create(
        code="KSO", defaults={"name": "Divisi KSO", "is_active": True},
    )


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0011_legal_umum_staff_roles")]

    operations = [migrations.RunPython(update_divisions, migrations.RunPython.noop)]
