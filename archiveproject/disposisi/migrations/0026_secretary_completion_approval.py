from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('disposisi', '0025_disposisirecipient_completed_by'),
    ]

    operations = [
        migrations.AlterField(
            model_name='disposisi',
            name='status_pengajuan',
            field=models.CharField(
                choices=[
                    ('DIBUAT', 'Disposisi Telah Dibuat'),
                    ('DIAJUKAN', 'Disposisi Telah Diajukan'),
                    ('DIISI', 'Disposisi Telah Diisi'),
                    ('DIBAGIKAN', 'Disposisi Telah Dibagikan'),
                    ('VERIFIKASI', 'Menunggu Persetujuan Sekretaris'),
                    ('SELESAI', 'Disposisi Telah Selesai'),
                ],
                default='DIBUAT',
                max_length=10,
            ),
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
                    ('AJUKAN_SELESAI', 'Diajukan ke Sekretaris'),
                    ('SELESAI', 'Selesai'),
                ],
                default='DIBUAT',
                max_length=20,
            ),
        ),
    ]
