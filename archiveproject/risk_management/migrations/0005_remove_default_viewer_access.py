from django.db import migrations, models


def remove_viewers(apps, schema_editor):
    apps.get_model("risk_management", "RiskAccess").objects.filter(role="viewer").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("risk_management", "0004_multiple_roles_per_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="riskaccess",
            name="role",
            field=models.CharField(
                choices=[
                    ("head_manager", "Kepala Manajemen Risiko"),
                    ("manager_member", "Anggota Manajemen Risiko"),
                    ("risk_officer", "Risk Officer"),
                    ("division_head", "Kepala Divisi"),
                ],
                max_length=30,
            ),
        ),
        migrations.RunPython(remove_viewers, migrations.RunPython.noop),
    ]
