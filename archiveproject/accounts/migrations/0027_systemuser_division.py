from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0026_systemuser_job_description")]

    operations = [
        migrations.AddField(
            model_name="systemuser",
            name="division",
            field=models.CharField(
                "Divisi",
                max_length=120,
                blank=True,
                default="",
                choices=[
                    ("", "Berdasarkan username"),
                    ("Direksi", "Direksi"),
                    ("Divisi Akuntansi", "Divisi Akuntansi"),
                    ("Divisi Aset", "Divisi Aset"),
                    ("Divisi Keuangan", "Divisi Keuangan"),
                    ("Divisi Legal dan Umum", "Divisi Legal dan Umum"),
                    ("Divisi Manajemen Risiko", "Divisi Manajemen Risiko"),
                    ("Divisi Sekretaris", "Divisi Sekretaris"),
                    ("Divisi Satuan Pengawas Internal", "Divisi Satuan Pengawas Internal"),
                    ("Divisi Umum", "Divisi Umum"),
                    ("Humas", "Humas"),
                    ("HRD", "HRD"),
                    ("Wirajatim KSO", "Wirajatim KSO"),
                    ("Divisi Umum & Legal", "Divisi Umum & Legal"),
                    ("Lainnya", "Lainnya"),
                ],
            ),
        ),
    ]
