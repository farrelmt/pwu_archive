from django.db import migrations, models
import inventory.models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0006_inventory_report_workflow")]
    operations = [
        migrations.AlterField(
            model_name="inventoryitem", name="received_date",
            field=models.DateField("Tanggal diterima", blank=True, null=True),
        ),
        migrations.AddField(
            model_name="inventoryitem", name="photo",
            field=models.ImageField("Foto barang", upload_to=inventory.models.inventory_photo_path, blank=True),
        ),
    ]
