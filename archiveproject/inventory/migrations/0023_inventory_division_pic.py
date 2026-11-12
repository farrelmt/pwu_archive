from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0022_request_submitted_on")]

    operations = [
        migrations.AddField(
            model_name="inventoryaccess",
            name="division",
            field=models.CharField(blank=True, choices=[
                ("", "Tidak ditentukan"), ("Direksi", "Direksi"),
                ("Divisi Akuntansi", "Divisi Akuntansi"), ("Divisi Aset", "Divisi Aset"),
                ("Divisi Keuangan", "Divisi Keuangan"), ("Divisi Legal dan Umum", "Divisi Legal dan Umum"),
                ("Divisi Manajemen Risiko", "Divisi Manajemen Risiko"), ("Divisi Sekretaris", "Divisi Sekretaris"),
                ("Divisi Satuan Pengawas Internal", "Divisi Satuan Pengawas Internal"),
                ("Divisi Umum", "Divisi Umum"), ("Humas", "Humas"), ("HRD", "HRD"),
                ("Wirajatim KSO", "Wirajatim KSO"), ("Divisi Umum & Legal", "Divisi Umum & Legal"),
                ("Lainnya", "Lainnya"),
            ], max_length=120, verbose_name="Divisi PIC"),
        ),
        migrations.AlterField(
            model_name="inventoryaccess", name="role",
            field=models.CharField(choices=[
                ("manager", "Manajer Inventaris"), ("officer", "Petugas Inventaris"),
                ("division_pic", "PIC Divisi Inventaris"), ("participant", "Peserta Inventaris"),
            ], max_length=20),
        ),
    ]
