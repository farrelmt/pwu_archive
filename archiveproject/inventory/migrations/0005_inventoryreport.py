import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0004_expand_it_asset_categories"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("report_type", models.CharField(choices=[("damaged", "Barang Rusak"), ("complaint", "Keluhan Penggunaan"), ("other", "Masalah Lainnya")], max_length=20, verbose_name="Jenis laporan")),
                ("description", models.TextField(verbose_name="Keluhan atau kerusakan")),
                ("status", models.CharField(choices=[("open", "Menunggu Tindakan"), ("in_progress", "Sedang Ditangani"), ("resolved", "Selesai")], default="open", max_length=20)),
                ("resolution_note", models.TextField(blank=True, verbose_name="Tindak lanjut")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="inventory.inventoryitem", verbose_name="Barang inventaris")),
                ("reporter", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_reports", to=settings.AUTH_USER_MODEL, verbose_name="Pelapor")),
            ],
            options={"verbose_name": "Laporan inventaris", "verbose_name_plural": "Laporan inventaris", "ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="inventoryreport", index=models.Index(fields=["status", "created_at"], name="inv_report_status_idx")),
        migrations.AddIndex(model_name="inventoryreport", index=models.Index(fields=["item", "status"], name="inv_report_item_idx")),
    ]
