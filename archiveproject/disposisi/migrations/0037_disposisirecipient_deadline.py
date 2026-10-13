from django.db import migrations, models


def copy_existing_deadlines(apps, schema_editor):
    DisposisiRecipient = apps.get_model("disposisi", "DisposisiRecipient")
    recipients = list(DisposisiRecipient.objects.filter(
        disposisi__deadline__isnull=False,
    ).select_related("disposisi"))
    for recipient in recipients:
        recipient.deadline = recipient.disposisi.deadline
    if recipients:
        DisposisiRecipient.objects.bulk_update(recipients, ["deadline"])


class Migration(migrations.Migration):
    dependencies = [
        ("disposisi", "0036_disposisi_dirut_secretary_review"),
    ]

    operations = [
        migrations.AddField(
            model_name="disposisirecipient",
            name="deadline",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RunPython(copy_existing_deadlines, migrations.RunPython.noop),
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
                    ("AKTIVITAS_PENERIMA", "Tindak Lanjut Penerima"),
                    ("AJUKAN_SELESAI", "Diajukan ke Sekretaris"),
                    ("SELESAI", "Selesai"),
                ],
                default="DIBUAT",
                max_length=20,
            ),
        ),
    ]
