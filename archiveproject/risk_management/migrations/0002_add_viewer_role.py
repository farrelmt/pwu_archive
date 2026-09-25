from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0001_initial")]
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
                    ("viewer", "Pembaca Risiko"),
                ],
                max_length=30,
            ),
        ),
    ]
