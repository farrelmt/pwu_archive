from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0012_add_inventory_user_role")]
    operations = [
        migrations.AlterField(
            model_name="systemuser",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Admin"), ("sekretaris", "Sekretaris"),
                    ("kadiv", "Kepala Divisi"), ("direktur", "Direktur"),
                    ("direktur_utama", "Direktur Utama"),
                    ("direktur_umum", "Direktur Umum"),
                    ("kadiv_akuntansi", "Kepala Divisi Akuntansi"),
                    ("kadiv_keuangan", "Kepala Divisi Keuangan"),
                    ("kadiv_risiko", "Kepala Divisi Manajemen Risiko"),
                    ("kadiv_legal_umum", "Kepala Divisi Legal dan Umum"),
                    ("kadiv_aset", "Kepala Divisi Aset"),
                    ("kadiv_spi", "Kepala SPI"), ("akuntan", "Akuntan"),
                    ("risk", "Pengguna Manajemen Risiko"),
                    ("inventory", "Pengguna Inventaris"),
                    ("employee", "Pegawai"),
                    ("wirajatim_kso", "Wirajatim KSO"),
                ],
                max_length=30,
            ),
        ),
    ]
