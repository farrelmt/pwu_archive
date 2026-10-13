from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("disposisi", "0035_disposisi_suggested_recipient_roles"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="disposisi",
            name="dirut_reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="disposisi",
            name="dirut_reviewed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviewed_dirut_dispositions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="disposisilog",
            name="action_log",
            field=models.CharField(
                choices=[
                    ("DIBUAT", "Telah Dibuat"),
                    ("DIEDIT", "Telah Diedit"),
                    ("UPLOAD_DISPOSISI", "File Telah Di Upload"),
                    ("AJUKAN_DISPOSISI", "Diajukan"),
                    ("BATAL_PENGAJUAN", "Pengajuan Dibatalkan"),
                    ("TOLAK_DISPOSISI", "Pengajuan Ditolak"),
                    ("SETUJUI_DISPOSISI", "Pengajuan Disetujui"),
                    ("TINJAU_DIRUT", "Isi Dirut Ditinjau Sekretaris"),
                    ("ISI_DISPOSISI", "Diisi"),
                    ("BAGI_DISPOSISI", "Dibagi"),
                    ("TERIMA_DISPOSISI", "Diterima Penerima"),
                    ("AKTIVITAS_PENERIMA", "Aktivitas Penerima"),
                    ("AJUKAN_SELESAI", "Diajukan ke Sekretaris"),
                    ("SELESAI", "Selesai"),
                ],
                default="DIBUAT",
                max_length=20,
            ),
        ),
    ]
