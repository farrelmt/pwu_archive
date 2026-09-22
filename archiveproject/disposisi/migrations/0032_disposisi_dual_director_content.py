from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('disposisi', '0031_disposisirecipient_follow_up_result'),
    ]

    operations = [
        migrations.AddField(
            model_name='disposisi',
            name='isi_disposisi_direktur',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='disposisi',
            name='isi_disposisi_dirut',
            field=models.TextField(blank=True, default=''),
        ),
    ]
