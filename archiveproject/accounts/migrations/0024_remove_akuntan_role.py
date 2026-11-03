from django.db import migrations, models


def convert_akuntan_users(apps, schema_editor):
    SystemUser = apps.get_model("accounts", "SystemUser")
    CompanyMember = apps.get_model("inventory", "CompanyMember")
    database = schema_editor.connection.alias
    accountant_ids = list(
        SystemUser.objects.using(database).filter(role="akuntan").values_list("pk", flat=True)
    )
    SystemUser.objects.using(database).filter(pk__in=accountant_ids).update(role="employee")
    CompanyMember.objects.using(database).filter(user_id__in=accountant_ids).update(
        position="Pegawai"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0023_rename_direktur_umum_label"),
        ("inventory", "0009_sync_portal_members"),
    ]

    operations = [
        migrations.RunPython(convert_akuntan_users, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="systemuser",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Admin"),
                    ("sekretaris", "Sekretaris"),
                    ("kadiv", "Kepala Divisi"),
                    ("direktur", "Direktur"),
                    ("direktur_utama", "Direktur Utama"),
                    ("direktur_umum", "Direktur"),
                    ("kadiv_akuntansi", "Kepala Divisi Akuntansi"),
                    ("kadiv_keuangan", "Kepala Divisi Keuangan"),
                    ("kadiv_risiko", "Kepala Divisi Manajemen Risiko"),
                    ("kadiv_legal_umum", "Kepala Divisi Legal dan Umum"),
                    ("kadiv_aset", "Kepala Divisi Aset"),
                    ("kadiv_spi", "Kepala SPI"),
                    ("risk", "Pengguna Manajemen Risiko"),
                    ("inventory", "Pengguna Inventaris"),
                    ("employee", "Pegawai"),
                    ("wirajatim_kso", "Wirajatim KSO"),
                ],
                max_length=30,
            ),
        ),
    ]
