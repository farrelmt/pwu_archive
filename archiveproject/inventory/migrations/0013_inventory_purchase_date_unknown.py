from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0012_inventory_purchase_date")]

    operations = [
        migrations.AddField(
            model_name="inventoryitem",
            name="purchase_date_unknown",
            field=models.BooleanField(
                default=False, verbose_name="Tanggal pembelian tidak diketahui"
            ),
        ),
    ]
