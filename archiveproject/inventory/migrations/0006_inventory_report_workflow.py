from django.db import migrations, models


def migrate_report_statuses(apps, schema_editor):
    InventoryReport = apps.get_model("inventory", "InventoryReport")
    InventoryReport.objects.filter(status="open").update(status="reported")
    InventoryReport.objects.filter(status="in_progress").update(status="verified")


class Migration(migrations.Migration):
    dependencies = [("inventory", "0005_inventoryreport")]

    operations = [
        migrations.RunPython(migrate_report_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="inventoryreport",
            name="status",
            field=models.CharField(
                choices=[
                    ("reported", "Laporan"),
                    ("verified", "Verifikasi"),
                    ("proposed", "Pengajuan"),
                    ("handed_over", "Penyerahan"),
                    ("resolved", "Selesai"),
                ],
                default="reported",
                max_length=20,
            ),
        ),
    ]
