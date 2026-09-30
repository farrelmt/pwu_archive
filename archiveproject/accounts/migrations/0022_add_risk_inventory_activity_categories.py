from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0021_clear_existing_emails"),
    ]

    operations = [
        migrations.AlterField(
            model_name="activitylog",
            name="category",
            field=models.CharField(
                choices=[
                    ("AUTH", "Authentication"),
                    ("DISPOSISI", "Disposisi"),
                    ("ACCOUNT", "Account"),
                    ("SYSTEM", "System"),
                    ("KOPERASI", "Koperasi"),
                    ("RISK", "Manajemen Risiko"),
                    ("INVENTORY", "Inventaris"),
                ],
                max_length=20,
            ),
        ),
    ]
