import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0015_software_account_credentials"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InternetPackageHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sim_number", models.CharField(blank=True, max_length=40, verbose_name="Nomor SIM")),
                ("operator", models.CharField(blank=True, max_length=100, verbose_name="Operator")),
                ("person_in_charge", models.CharField(blank=True, max_length=180, verbose_name="Penanggung jawab nomor")),
                ("package_name", models.CharField(max_length=180, verbose_name="Paket internet")),
                ("effective_on", models.DateField(default=django.utils.timezone.localdate, verbose_name="Mulai berlaku")),
                ("expires_on", models.DateField(verbose_name="Batas berlaku")),
                ("notes", models.TextField(blank=True, verbose_name="Catatan")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="internet_packages", to="inventory.inventoryitem", verbose_name="Router / modem")),
            ],
            options={
                "verbose_name": "Riwayat paket internet",
                "verbose_name_plural": "Riwayat paket internet",
                "ordering": ["-effective_on", "-created_at", "-pk"],
                "indexes": [models.Index(fields=["item", "-effective_on"], name="inv_pkg_item_date_idx")],
            },
        ),
    ]
