from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("risk_management", "0019_order_monitoring_actions_by_treatment"),
    ]

    operations = [
        migrations.AddField(
            model_name="riskmonitoring",
            name="is_priority",
            field=models.BooleanField(default=False, verbose_name="Prioritas Risiko"),
        ),
    ]
