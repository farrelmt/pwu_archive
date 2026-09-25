from django.db import migrations, models


def make_everyone_participant(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    InventoryAccess = apps.get_model("inventory", "InventoryAccess")
    InventoryAccess.objects.filter(role="viewer").update(role="participant")
    for user_id in User.objects.filter(is_active=True).values_list("pk", flat=True):
        InventoryAccess.objects.get_or_create(
            user_id=user_id,
            defaults={"role": "participant", "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0002_shared_accounts_and_company_members"),
    ]

    operations = [
        migrations.AlterField(
            model_name="inventoryaccess",
            name="role",
            field=models.CharField(
                choices=[
                    ("manager", "Manajer Inventaris"),
                    ("officer", "Petugas Inventaris"),
                    ("participant", "Peserta Inventaris"),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(make_everyone_participant, migrations.RunPython.noop),
    ]
