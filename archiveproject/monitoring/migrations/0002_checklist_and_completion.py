import django.db.models.deletion
from django.db import migrations, models


def backfill_completion(apps, schema_editor):
    Assignment = apps.get_model("monitoring", "Assignment")
    Assignment.objects.filter(status="done").update(completed_at=models.F("updated_at"))


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="assignment",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Selesai pada"),
        ),
        migrations.CreateModel(
            name="ChecklistItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.CharField(max_length=220, verbose_name="Langkah")),
                ("is_done", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assignment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="checklist_items", to="monitoring.assignment")),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
        migrations.RunPython(backfill_completion, migrations.RunPython.noop),
    ]
