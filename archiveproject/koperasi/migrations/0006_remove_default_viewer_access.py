from django.db import migrations, models


def remove_viewers(apps, schema_editor):
    apps.get_model("koperasi", "KoperasiAccess").objects.filter(role="viewer").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("koperasi", "0005_multiple_roles_per_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="koperasiaccess",
            name="role",
            field=models.CharField(
                choices=[
                    ("chairman", "Ketua Koperasi"),
                    ("treasurer", "Bendahara"),
                    ("savings_treasurer", "Bendahara Sie Simpan Pinjam"),
                    ("business_treasurer", "Bendahara Sie Usaha"),
                    ("member_section", "Sie Anggota"),
                    ("secretary", "Sekretaris Koperasi"),
                    ("supervisor", "Pengawas"),
                    ("admin", "Administrator Koperasi"),
                    ("manager", "Manajer Koperasi"),
                    ("finance", "Keuangan"),
                    ("officer", "Petugas"),
                    ("auditor", "Auditor"),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(remove_viewers, migrations.RunPython.noop),
    ]
