from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0010_optional_risk_scores")]

    operations = [
        migrations.AlterField(
            model_name="riskaccess", name="role",
            field=models.CharField(max_length=30, choices=[
                ("head_manager", "Kepala Manajemen Risiko"),
                ("manager_member", "Anggota Manajemen Risiko"),
                ("risk_officer", "Risk Officer"),
                ("division_head", "Kepala Divisi"),
                ("staff_it", "Staff IT"),
                ("staff_hrd", "HRD"),
                ("staff_humas", "Humas"),
            ]),
        ),
    ]
