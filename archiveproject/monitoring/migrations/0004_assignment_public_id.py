import uuid

from django.db import migrations, models


def assign_public_ids(apps, schema_editor):
    Assignment = apps.get_model("monitoring", "Assignment")
    for assignment in Assignment.objects.all().iterator():
        Assignment.objects.filter(pk=assignment.pk).update(public_id=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0003_checklist_groups")]

    operations = [
        migrations.AddField(
            model_name="assignment",
            name="public_id",
            field=models.UUIDField(blank=True, null=True, editable=False),
        ),
        migrations.RunPython(assign_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="assignment",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
