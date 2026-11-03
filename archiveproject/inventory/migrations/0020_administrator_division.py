from django.db import migrations


def update_division(apps, schema_editor):
    apps.get_model("inventory", "CompanyMember").objects.filter(division="Administrator Sistem").update(division="Divisi Umum & Legal")
    apps.get_model("inventory", "InventoryRequest").objects.filter(division="Administrator Sistem").update(division="Divisi Umum & Legal")


class Migration(migrations.Migration):
    dependencies = [("inventory", "0019_inventoryrequest")]
    operations = [migrations.RunPython(update_division, migrations.RunPython.noop)]
