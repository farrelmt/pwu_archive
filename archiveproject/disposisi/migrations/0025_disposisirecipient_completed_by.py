from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('disposisi', '0024_recipient_activity_workflow'),
    ]

    operations = [
        migrations.AddField(
            model_name='disposisirecipient',
            name='completed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='completed_disposisi_recipients',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
