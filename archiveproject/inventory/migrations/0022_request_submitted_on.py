from django.db import migrations, models
from django.utils import timezone


def backfill_dates(apps, schema_editor):
    Request = apps.get_model("inventory", "InventoryRequest")
    for entry in Request.objects.using(schema_editor.connection.alias).iterator():
        entry.submitted_on = timezone.localtime(entry.created_at).date()
        entry.save(update_fields=["submitted_on"])


class Migration(migrations.Migration):
    dependencies = [("inventory", "0021_request_public_id")]
    operations = [
        migrations.AddField(model_name="inventoryrequest", name="submitted_on", field=models.DateField(null=True, verbose_name="Tanggal pengajuan")),
        migrations.RunPython(backfill_dates, migrations.RunPython.noop),
        migrations.AlterField(model_name="inventoryrequest", name="submitted_on", field=models.DateField(default=timezone.localdate, verbose_name="Tanggal pengajuan")),
    ]
