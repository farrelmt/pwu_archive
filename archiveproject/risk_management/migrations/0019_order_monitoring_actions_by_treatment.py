from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0018_link_monitoring_actions_to_treatments")]

    operations = [
        migrations.AlterModelOptions(
            name="riskactionplan",
            options={
                "ordering": ["treatment_id", "pk"],
                "verbose_name": "Rencana aksi risiko",
                "verbose_name_plural": "Rencana aksi risiko",
            },
        ),
    ]
