from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("risk_management", "0003_riskmonitoring_riskactionplan"),
    ]

    operations = [
        migrations.AlterField(
            model_name="riskaccess",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="risk_accesses",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="riskaccess",
            constraint=models.UniqueConstraint(
                fields=("user", "role", "division"),
                name="unique_risk_user_role_division",
                nulls_distinct=False,
            ),
        ),
    ]
