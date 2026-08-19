from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations, models


ORGANIZATION_USERS = [
    ("koperasi_ketua", "Diaz", "Ilyasa", "chairman"),
    ("koperasi_pengawas_1", "Eddy", "Santoso", "supervisor"),
    ("koperasi_pengawas_2", "Hadi", "Kusmiarto", "supervisor"),
    ("koperasi_sekretaris", "Mita", "Febrianti", "secretary"),
    ("koperasi_bendahara", "Irsalina", "N.H", "treasurer"),
    ("koperasi_sie_anggota", "Bayu", "Aji M.P.P", "member_section"),
    ("koperasi_sie_usaha_1", "Putu", "Sherlyna A.P", "business_treasurer"),
    ("koperasi_sie_usaha_2", "Praditya", "Hudi", "business_treasurer"),
    ("koperasi_sie_usaha_3", "Angga", "Prasetyo", "business_treasurer"),
    (
        "koperasi_sie_simpan_pinjam",
        "Anik",
        "Susma Wardani",
        "savings_treasurer",
    ),
]


def seed_organization_users(apps, schema_editor):
    SystemUser = apps.get_model("accounts", "SystemUser")
    KoperasiAccess = apps.get_model("koperasi", "KoperasiAccess")

    for username, first_name, last_name, koperasi_role in ORGANIZATION_USERS:
        user, created = SystemUser.objects.get_or_create(
            username=username,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "email": "it.pwujatim@gmail.com",
                "role": "akuntan",
                "is_active": True,
                "password": make_password(username),
            },
        )
        update_fields = []
        if user.first_name != first_name:
            user.first_name = first_name
            update_fields.append("first_name")
        if user.last_name != last_name:
            user.last_name = last_name
            update_fields.append("last_name")
        if user.role != "akuntan":
            user.role = "akuntan"
            update_fields.append("role")
        if not user.is_active:
            user.is_active = True
            update_fields.append("is_active")
        if not user.email:
            user.email = "it.pwujatim@gmail.com"
            update_fields.append("email")
        if update_fields:
            user.save(update_fields=update_fields)

        access, _ = KoperasiAccess.objects.get_or_create(
            user=user,
            company=None,
            defaults={"role": koperasi_role, "is_active": True},
        )
        access_updates = []
        if access.role != koperasi_role:
            access.role = koperasi_role
            access_updates.append("role")
        if not access.is_active:
            access.is_active = True
            access_updates.append("is_active")
        if access_updates:
            access.save(update_fields=access_updates)


class Migration(migrations.Migration):
    dependencies = [
        ("koperasi", "0003_cashtransaction_account_cashtransaction_counterparty_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
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
                    ("viewer", "Pembaca"),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(seed_organization_users, migrations.RunPython.noop),
    ]
