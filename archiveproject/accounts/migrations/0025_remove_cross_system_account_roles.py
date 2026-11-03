from django.db import migrations, models


OLD_ROLES = ("risk", "inventory", "wirajatim_kso")


def convert_users_to_employee(apps, schema_editor):
    SystemUser = apps.get_model("accounts", "SystemUser")
    CompanyMember = apps.get_model("inventory", "CompanyMember")
    database = schema_editor.connection.alias
    user_ids = list(
        SystemUser.objects.using(database)
        .filter(role__in=OLD_ROLES)
        .values_list("pk", flat=True)
    )
    SystemUser.objects.using(database).filter(pk__in=user_ids).update(role="employee")
    CompanyMember.objects.using(database).filter(user_id__in=user_ids).update(
        position="Pegawai"
    )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0024_remove_akuntan_role")]

    operations = [
        migrations.RunPython(convert_users_to_employee, migrations.RunPython.noop),
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
                    ("employee", "Pegawai"),
                ],
                max_length=30,
            ),
        ),
    ]
