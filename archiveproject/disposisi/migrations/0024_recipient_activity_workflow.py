from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('disposisi', '0023_alter_disposisi_tujuan'),
    ]

    operations = [
        migrations.AddField(
            model_name='disposisirecipient',
            name='activity_description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='disposisirecipient',
            name='received_at',
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
                    ('TERIMA_DISPOSISI', 'Diterima Penerima'),
                    ('AKTIVITAS_PENERIMA', 'Aktivitas Penerima'),
                    ('SELESAI', 'Selesai'),
                ],
                default='DIBUAT',
                max_length=20,
            ),
        ),
    ]
