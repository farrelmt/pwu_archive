from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0011_ownership_asset_codes")]

    operations = [
        migrations.AddField(
            model_name="inventoryitem",
            name="purchase_date",
            field=models.DateField(blank=True, null=True, verbose_name="Tanggal pembelian"),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="received_date_same_as_purchase",
            field=models.BooleanField(
                default=False, verbose_name="Tanggal diterima sama dengan tanggal pembelian"
            ),
        ),
    ]
