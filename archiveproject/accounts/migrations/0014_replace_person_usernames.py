from django.contrib.auth.hashers import make_password
from django.db import migrations


USERNAME_CHANGES = {
    "erik_hendra_wibisono": "akuntansi_0",
    "arsyad_fauzan": "akuntansi_1",
    "panji_samudra_pangestu": "akuntansi_2",
    "moch_arya_rake_baihaqi": "aset_0",
    "ryan_winardo": "aset_1",
    "yanwar_awaludin": "keuangan_0",
    "indriyan_lukman": "keuangan_1",
    "rahmad_one_rudy_santoso": "keuangan_2",
    "rivo_henardus_surupandy": "legal_umum_0",
    "jessy_yolandita_dewi": "legal_0",
    "evelyn_winarko": "legal_1",
    "anggi": "legal_2",
    "hendra_purnama": "manajemen_risiko_0",
    "yucea_variegata_heranda": "manajemen_risiko_1",
    "alzira_pramitha": "sekretaris_0",
    "wiwin_eko_saputro": "sekretaris_1",
    "charles_rante_batara": "spi_0",
    "fachrudin_m": "spi_1",
    "rafika_sari": "spi_2",
    "firda_tiberias": "spi_3",
    "ernanda_roeswindhi_andika": "umum_0",
    "farrel_muhammad_taqi": "umum_1",
    "harnoko": "umum_2",
    "rofiti": "umum_3",
    "suwarno": "umum_4",
    "sugeng_rahmad_basuki": "umum_5",
    "muhamad_muadz": "umum_6",
    "ferry_sugiarto": "umum_7",
    "hernowo_wedya_sasongko": "umum_8",
    "endri_rianto": "umum_9",
    "rico_triawan": "umum_10",
}


def rename_users(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    for old_username, new_username in USERNAME_CHANGES.items():
        user = User.objects.filter(username=old_username).first()
        if user is None:
            continue
        if User.objects.filter(username=new_username).exclude(pk=user.pk).exists():
            raise RuntimeError(f"Username tujuan sudah digunakan: {new_username}")
        user.username = new_username
        user.password = make_password(new_username)
        user.save(update_fields=["username", "password"])


def restore_users(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    for old_username, new_username in reversed(tuple(USERNAME_CHANGES.items())):
        user = User.objects.filter(username=new_username).first()
        if user is None:
            continue
        if User.objects.filter(username=old_username).exclude(pk=user.pk).exists():
            raise RuntimeError(f"Username lama sudah digunakan: {old_username}")
        user.username = old_username
        user.password = make_password(old_username)
        user.save(update_fields=["username", "password"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0013_add_employee_role"),
    ]

    operations = [
        migrations.RunPython(rename_users, restore_users),
    ]
