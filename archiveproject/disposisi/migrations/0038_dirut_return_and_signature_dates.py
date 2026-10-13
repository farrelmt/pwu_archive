from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('disposisi', '0037_disposisirecipient_deadline'),
    ]

    operations = [
        migrations.AddField(
            model_name='disposisi',
            name='isi_disposisi_dirut_draft',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='disposisi',
            name='dirut_signed_on',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='disposisi',
            name='direktur_signed_on',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='disposisi',
            name='signed_on',
            field=models.DateField(blank=True, null=True),
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
                    ('TINJAU_DIRUT', 'Isi Dirut Ditinjau Sekretaris'),
                    ('KEMBALIKAN_DIRUT', 'Isi Dirut Dikembalikan Sekretaris'),
                    ('ISI_DISPOSISI', 'Diisi'),
                    ('BAGI_DISPOSISI', 'Dibagi'),
                    ('TERIMA_DISPOSISI', 'Diterima Penerima'),
                    ('AKTIVITAS_PENERIMA', 'Tindak Lanjut Penerima'),
                    ('AJUKAN_SELESAI', 'Diajukan ke Sekretaris'),
                    ('SELESAI', 'Selesai'),
                ],
                default='DIBUAT',
                max_length=20,
            ),
        ),
    ]
