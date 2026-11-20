import django.db.models.deletion
from django.db import migrations, models


def group_existing_items(apps, schema_editor):
    Assignment = apps.get_model("monitoring", "Assignment")
    ChecklistGroup = apps.get_model("monitoring", "ChecklistGroup")
    ChecklistItem = apps.get_model("monitoring", "ChecklistItem")
    for assignment in Assignment.objects.all().iterator():
        group = ChecklistGroup.objects.create(assignment_id=assignment.pk, title="Tugas")
        ChecklistItem.objects.filter(assignment_id=assignment.pk).update(group_id=group.pk)


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0002_checklist_and_completion")]

    operations = [
        migrations.CreateModel(
            name="ChecklistGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120, verbose_name="Judul checklist")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assignment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="checklist_groups", to="monitoring.assignment")),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
        migrations.AddField(
            model_name="checklistitem",
            name="group",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="items", to="monitoring.checklistgroup"),
        ),
        migrations.RunPython(group_existing_items, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="checklistitem",
            name="group",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="monitoring.checklistgroup"),
        ),
    ]
