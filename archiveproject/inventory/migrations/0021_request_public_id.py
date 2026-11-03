import uuid

from django.db import migrations, models
import inventory.models


def populate_public_ids(apps, schema_editor):
    Request = apps.get_model("inventory", "InventoryRequest")
    for entry in Request.objects.using(schema_editor.connection.alias).filter(public_id__isnull=True).iterator():
        entry.public_id = uuid.uuid4().hex
        entry.save(update_fields=["public_id"])


class Migration(migrations.Migration):
    dependencies = [("inventory", "0020_administrator_division")]
    operations = [
        migrations.AddField(model_name="inventoryrequest", name="public_id", field=models.CharField(max_length=32, null=True, unique=True, editable=False)),
        migrations.RunPython(populate_public_ids, migrations.RunPython.noop),
        migrations.AlterField(model_name="inventoryrequest", name="public_id", field=models.CharField(default=inventory.models.generate_request_public_id, max_length=32, unique=True, editable=False)),
    ]
