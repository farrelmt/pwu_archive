from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('disposisi', '0030_disposisi_deadline'),
    ]

    operations = [
        migrations.AddField(
            model_name='disposisirecipient',
            name='follow_up_result',
            field=models.TextField(blank=True, default=''),
        ),
    ]
