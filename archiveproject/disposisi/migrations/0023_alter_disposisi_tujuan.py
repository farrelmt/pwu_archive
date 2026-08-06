from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('disposisi', '0022_disposisirecipient_agreed_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='disposisi',
            name='tujuan',
            field=models.CharField(
                choices=[
                    ('DIRUT', 'Direktur Utama'),
                    ('DIR', 'Direktur'),
                    ('DIREKSI', 'Direksi'),
                ],
                max_length=20,
            ),
        ),
    ]
