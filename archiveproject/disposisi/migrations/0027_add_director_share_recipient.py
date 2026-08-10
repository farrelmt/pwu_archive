from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('disposisi', '0026_secretary_completion_approval'),
    ]

    operations = [
        migrations.AlterField(
            model_name='disposisirecipient',
            name='role',
            field=models.CharField(
                choices=[
                    ('direktur_utama', 'Direktur Utama'),
                    ('direktur', 'Direktur'),
                    ('direktur_umum', 'Direktur Umum'),
                    ('kadiv_akuntansi', 'Kepala Divisi Akuntansi'),
                    ('kadiv_keuangan', 'Kepala Divisi Keuangan'),
                    ('kadiv_risiko', 'Kepala Divisi Manajemen Risiko'),
                    ('kadiv_legal_umum', 'Kepala Divisi Legal dan Umum'),
                    ('kadiv_aset', 'Kepala Divisi Aset'),
                    ('kadiv_spi', 'Kepala Divisi SPI'),
                ],
                max_length=30,
            ),
        ),
    ]
