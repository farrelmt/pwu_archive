from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0018_software_billing_details"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_type", models.CharField(choices=[("procurement", "Pengadaan Barang / Jasa"), ("repair", "Perbaikan Barang")], max_length=20, verbose_name="Jenis permintaan")),
                ("purpose", models.TextField(verbose_name="Keperluan")),
                ("items", models.JSONField(default=list, verbose_name="Daftar barang / jasa")),
                ("applicant_name", models.CharField(max_length=180, verbose_name="Nama lengkap")),
                ("division", models.CharField(blank=True, max_length=120, verbose_name="Divisi")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Permintaan", "verbose_name_plural": "Permintaan", "ordering": ["-created_at"]},
        ),
    ]
