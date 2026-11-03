import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def move_sim_details_to_cards(apps, schema_editor):
    History = apps.get_model("inventory", "InternetPackageHistory")
    SimCard = apps.get_model("inventory", "InternetSimCard")
    db_alias = schema_editor.connection.alias
    for entry in History.objects.using(db_alias).order_by("pk").iterator():
        if not (entry.sim_number or entry.operator or entry.person_in_charge):
            continue
        sim_card, _ = SimCard.objects.using(db_alias).get_or_create(
            item_id=entry.item_id,
            sim_number=entry.sim_number,
            operator=entry.operator,
            person_in_charge=entry.person_in_charge,
            defaults={"created_by_id": entry.created_by_id},
        )
        History.objects.using(db_alias).filter(pk=entry.pk).update(sim_card_id=sim_card.pk)


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0016_internet_package_history"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InternetSimCard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sim_number", models.CharField(blank=True, max_length=40, verbose_name="Nomor SIM")),
                ("operator", models.CharField(blank=True, max_length=100, verbose_name="Operator")),
                ("person_in_charge", models.CharField(blank=True, max_length=180, verbose_name="Penanggung jawab nomor")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sim_cards", to="inventory.inventoryitem", verbose_name="Router / modem")),
            ],
            options={
                "verbose_name": "Kartu SIM internet",
                "verbose_name_plural": "Kartu SIM internet",
                "ordering": ["sim_number", "pk"],
            },
        ),
        migrations.AddField(
            model_name="internetpackagehistory",
            name="sim_card",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="package_history", to="inventory.internetsimcard", verbose_name="Kartu SIM"),
        ),
        migrations.RunPython(move_sim_details_to_cards, migrations.RunPython.noop),
    ]
