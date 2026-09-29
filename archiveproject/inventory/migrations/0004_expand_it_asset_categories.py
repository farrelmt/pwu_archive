from django.db import migrations, models


def categorize_existing_it_assets(apps, schema_editor):
    InventoryItem = apps.get_model("inventory", "InventoryItem")
    computer_keywords = ("laptop", "notebook", "computer", "komputer", "desktop", "pc")
    peripheral_keywords = ("keyboard", "mouse", "monitor", "headset", "webcam", "scanner", "printer")
    network_keywords = ("router", "switch", "access point", "modem", "firewall")

    for item in InventoryItem.objects.filter(category="hardware"):
        name = item.item_name.casefold()
        if any(keyword in name for keyword in computer_keywords):
            item.category = "computer"
        elif any(keyword in name for keyword in peripheral_keywords):
            item.category = "peripheral"
        elif any(keyword in name for keyword in network_keywords):
            item.category = "network"
        else:
            item.category = "component"
        item.save(update_fields=["category"])


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0003_inventory_participants"),
    ]

    operations = [
        migrations.AlterField(
            model_name="inventoryitem",
            name="category",
            field=models.CharField(
                choices=[
                    ("computer", "Komputer / Laptop"),
                    ("peripheral", "Periferal IT (Keyboard, Mouse, Monitor)"),
                    ("component", "Komponen Hardware"),
                    ("network", "Perangkat Jaringan"),
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
        migrations.RunPython(categorize_existing_it_assets, migrations.RunPython.noop),
    ]
