from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0013_inventory_purchase_date_unknown")]

    operations = [
        migrations.AlterField(
            model_name="inventoryitem",
            name="category",
            field=models.CharField(
                choices=[
                    ("computer", "Komputer"),
                    ("laptop", "Laptop"),
                    ("peripheral", "Periferal IT (Keyboard, Mouse, Monitor)"),
                    ("component", "Komponen Hardware"),
                    ("network", "Perangkat Jaringan"),
                    ("modem_wifi", "Modem/Wifi"),
                    ("software", "Software / Lisensi"),
                    ("hardware", "Perangkat Keras Lainnya"),
                    ("furniture", "Furnitur"),
                    ("vehicle", "Kendaraan"),
                    ("tool", "Peralatan Kerja"),
                    ("office", "Perlengkapan Kantor"),
                    ("other", "Lainnya"),
                ],
                max_length=20,
                verbose_name="Kategori",
            ),
        ),
    ]
