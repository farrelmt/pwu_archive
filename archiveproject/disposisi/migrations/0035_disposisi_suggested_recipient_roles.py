from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("disposisi", "0034_disposisi_disp_received_pk_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="disposisi",
            name="suggested_recipient_roles",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
