from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('disposisi', '0021_disposisirecipient'),
    ]

    operations = [
        migrations.AddField(
            model_name='disposisirecipient',
            name='agreed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='disposisilog',
            name='action_log',
            field=models.CharField(
                choices=[
                    ('DIBUAT', 'Telah Dibuat'),
                    ('DIEDIT', 'Telah Diedit'),
                    ('UPLOAD_DISPOSISI', 'File Telah Di Upload'),
                    ('AJUKAN_DISPOSISI', 'Diajukan'),
                    ('BATAL_PENGAJUAN', 'Pengajuan Dibatalkan'),
                    ('TOLAK_DISPOSISI', 'Pengajuan Ditolak'),
                    ('SETUJUI_DISPOSISI', 'Pengajuan Disetujui'),
                    ('ISI_DISPOSISI', 'Diisi'),
                    ('BAGI_DISPOSISI', 'Dibagi'),
                    ('TERIMA_DISPOSISI', 'Penerima Menyetujui'),
                    ('SELESAI', 'Selesai'),
                ],
                default='DIBUAT',
                max_length=20,
            ),
        ),
    ]
