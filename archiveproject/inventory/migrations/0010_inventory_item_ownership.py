from django.db import migrations, models


def mark_existing_personal_items(apps, schema_editor):
    InventoryItem = apps.get_model("inventory", "InventoryItem")
    InventoryItem.objects.filter(asset_code__startswith="PRIBADI-").update(ownership="personal")


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0009_sync_portal_members"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryitem",
            name="ownership",
            field=models.CharField(
                choices=[
                    ("company", "Company"),
                    ("lumbung", "Lumbung"),
                    ("personal", "Personal"),
                    ("third_party", "Third Party"),
                ],
                default="company",
                max_length=20,
                verbose_name="Kepemilikan",
            ),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="third_party_name",
            field=models.CharField(blank=True, max_length=180, verbose_name="Nama pihak ketiga"),
        ),
        migrations.RunPython(mark_existing_personal_items, migrations.RunPython.noop),
    ]
