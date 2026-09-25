from django.contrib.auth.hashers import make_password
from django.db import migrations


KOPERASI_RENAMES = {
    "koperasi_sie_simpan_pinjam": "akuntansi_3",
    "koperasi_pengawas_1": "aset_2",
    "koperasi_sie_anggota": "keuangan_3",
    "koperasi_ketua": "keuangan_4",
    "koperasi_bendahara": "keuangan_5",
    "koperasi_sie_usaha_2": "legal_3",
    "koperasi_sekretaris": "sekretaris_2",
    "koperasi_pengawas_2": "spi_4",
    "koperasi_sie_usaha_1": "umum_11",
    "koperasi_sie_usaha_3": "umum_12",
}

RISK_ROLE_TARGETS = {
    "risk_head_manager": "manajemen_risiko_0",
    "risk_manager_member": "manajemen_risiko_1",
    "risk_head_division_1": "akuntansi_0",
    "risk_head_division_2": "keuangan_0",
    "risk_head_division_3": "manajemen_risiko_0",
    "risk_head_division_4": "legal_umum_0",
    "risk_head_division_5": "aset_2",
    "risk_head_division_6": "spi_0",
}

DUMMY_USERNAMES = [
    "risk_head_division_1", "risk_head_division_2", "risk_head_division_3",
    "risk_head_division_4", "risk_head_division_5", "risk_head_division_6",
    "risk_head_division_7", "risk_head_division_8", "risk_head_division_9",
    "risk_head_manager", "risk_manager_member",
    "kadiv_akuntansi", "kadiv_aset", "kadiv_keuangan",
    "kadiv_legal_umum", "kadiv_risiko", "ka_spi",
    "inventory_manager", "inventory_officer", "inventory_viewer",
]


def consolidate(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    RiskAccess = apps.get_model("risk_management", "RiskAccess")

    for old_username, new_username in KOPERASI_RENAMES.items():
        user = User.objects.filter(username=old_username).first()
        if user is None:
            continue
        if User.objects.filter(username=new_username).exclude(pk=user.pk).exists():
            raise RuntimeError(f"Username tujuan sudah digunakan: {new_username}")
        user.username = new_username
        user.password = make_password(new_username)
        user.save(update_fields=["username", "password"])

    for source_username, target_username in RISK_ROLE_TARGETS.items():
        source = User.objects.filter(username=source_username).first()
        target = User.objects.filter(username=target_username).first()
        if source is None or target is None:
            continue
        for access in RiskAccess.objects.filter(user=source, is_active=True):
            RiskAccess.objects.get_or_create(
                user=target,
                role=access.role,
                division=access.division,
                defaults={"is_active": True},
            )

    User.objects.filter(username__in=DUMMY_USERNAMES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0015_consolidate_risk_officers_and_kso_accounts"),
        ("koperasi", "0005_multiple_roles_per_user"),
        ("risk_management", "0004_multiple_roles_per_user"),
    ]

    operations = [
        migrations.RunPython(consolidate, migrations.RunPython.noop),
    ]
