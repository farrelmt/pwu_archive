from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0014_modem_wifi_category")]

    operations = [
        migrations.AddField(
            model_name="inventoryitem", name="software_username",
            field=models.CharField("Username akun", max_length=180, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="inventoryitem", name="software_email",
            field=models.EmailField("Email akun", blank=True, null=True),
        ),
        migrations.AddField(
            model_name="inventoryitem", name="software_password_encrypted",
            field=models.TextField(blank=True, null=True, editable=False),
        ),
    ]
