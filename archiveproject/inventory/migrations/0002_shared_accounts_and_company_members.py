import django.db.models.deletion
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations, models


EMPLOYEES = [
    ("erik_hendra_wibisono", "Erik", "Hendra Wibisono", "PWU-AKT-001", "Akuntansi", "Kepala Divisi", "kadiv_akuntansi"),
    ("arsyad_fauzan", "Arsyad", "Fauzan", "PWU-AKT-002", "Akuntansi", "Anggota", "employee"),
    ("koperasi_sie_simpan_pinjam", "Anik", "Susma Wardani", "PWU-AKT-003", "Akuntansi", "Anggota", "employee"),
    ("panji_samudra_pangestu", "Panji", "Samudra Pangestu", "PWU-AKT-004", "Akuntansi", "Anggota", "employee"),
    ("koperasi_pengawas_1", "Eddy", "Santoso", "PWU-AST-001", "Aset", "Kepala Divisi", "kadiv_aset"),
    ("moch_arya_rake_baihaqi", "Moch. Arya", "Rake Baihaqi", "PWU-AST-002", "Aset", "Anggota", "employee"),
    ("ryan_winardo", "Ryan", "Winardo", "PWU-AST-003", "Aset", "Anggota", "employee"),
    ("yanwar_awaludin", "Yanwar", "Awaludin", "PWU-KEU-001", "Keuangan", "Kepala Divisi", "kadiv_keuangan"),
    ("koperasi_sie_anggota", "Bayu", "Aji Maha Putra P", "PWU-KEU-002", "Keuangan", "Anggota", "employee"),
    ("koperasi_ketua", "Diaz", "Ilyasa", "PWU-KEU-003", "Keuangan", "Anggota", "employee"),
    ("indriyan_lukman", "Indriyan", "Lukman", "PWU-KEU-004", "Keuangan", "Anggota", "employee"),
    ("rahmad_one_rudy_santoso", "Rahmad One", "Rudy Santoso", "PWU-KEU-005", "Keuangan", "Anggota", "employee"),
    ("rivo_henardus_surupandy", "Rivo Henardus", "Surupandy", "PWU-LGU-001", "Legal, Umum, Sekretaris", "Kepala Divisi", "kadiv_legal_umum"),
    ("koperasi_sie_usaha_2", "Praditya Hudi", "Trianawati", "PWU-LEG-002", "Legal", "Anggota", "employee"),
    ("jessy_yolandita_dewi", "Jessy Yolandita", "Dewi", "PWU-LEG-003", "Legal", "Anggota", "employee"),
    ("evelyn_winarko", "Evelyn", "Winarko", "PWU-LEG-004", "Legal", "Anggota", "employee"),
    ("anggi", "Anggi", "", "PWU-LEG-005", "Legal", "Anggota", "employee"),
    ("hendra_purnama", "Hendra", "Purnama, Ak., M.MT., CA, CRMP", "PWU-MRI-001", "Manajemen Risiko", "Kepala Divisi", "kadiv_risiko"),
    ("yucea_variegata_heranda", "Yucea Variegata", "Heranda", "PWU-MRI-002", "Manajemen Risiko", "Anggota", "employee"),
    ("koperasi_sie_usaha_1", "Putu Sherlyna", "Arini Putri", "PWU-UMM-002", "Umum", "Anggota", "employee"),
    ("ernanda_roeswindhi_andika", "Ernanda Roeswindhi", "Andika", "PWU-UMM-003", "Umum", "Anggota", "employee"),
    ("farrel_muhammad_taqi", "Farrel Muhammad", "Taqi", "PWU-UMM-004", "Umum", "Anggota", "employee"),
    ("harnoko", "Harnoko", "", "PWU-UMM-005", "Umum", "Anggota", "employee"),
    ("rofiti", "Rofiti", "", "PWU-UMM-006", "Umum", "Anggota", "employee"),
    ("suwarno", "Suwarno", "", "PWU-UMM-007", "Umum", "Anggota", "employee"),
    ("koperasi_sie_usaha_3", "Angga", "Prasetyo", "PWU-UMM-008", "Umum", "Anggota", "employee"),
    ("sugeng_rahmad_basuki", "Sugeng Rahmad", "Basuki R.H", "PWU-UMM-009", "Umum", "Anggota", "employee"),
    ("muhamad_muadz", "Muhamad", "Muadz", "PWU-UMM-010", "Umum", "Anggota", "employee"),
    ("ferry_sugiarto", "Ferry", "Sugiarto", "PWU-UMM-011", "Umum", "Anggota", "employee"),
    ("hernowo_wedya_sasongko", "Hernowo Wedya", "Sasongko", "PWU-UMM-012", "Umum", "Anggota", "employee"),
    ("endri_rianto", "Endri", "Rianto", "PWU-UMM-013", "Umum", "Anggota", "employee"),
    ("rico_triawan", "Rico", "Triawan", "PWU-UMM-014", "Umum", "Anggota", "employee"),
    ("alzira_pramitha", "Alzira", "Pramitha", "PWU-SEK-002", "Sekretaris", "Anggota", "employee"),
    ("wiwin_eko_saputro", "Wiwin Eko", "Saputro", "PWU-SEK-003", "Sekretaris", "Anggota", "employee"),
    ("koperasi_sekretaris", "Mita Febriyanti", "Dwi Restu", "PWU-SEK-004", "Sekretaris", "Anggota", "employee"),
    ("charles_rante_batara", "Charles Rante", "Batara, SE., MM., CFrA", "PWU-SPI-001", "Satuan Pengawas Internal", "Kepala Divisi", "kadiv_spi"),
    ("fachrudin_m", "Fachrudin", "M", "PWU-SPI-002", "Satuan Pengawas Internal", "Anggota", "employee"),
    ("rafika_sari", "Rafika", "Sari", "PWU-SPI-003", "Satuan Pengawas Internal", "Anggota", "employee"),
    ("firda_tiberias", "Firda", "Tiberias", "PWU-SPI-004", "Satuan Pengawas Internal", "Anggota", "employee"),
]


def seed_directory_and_access(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    CompanyMember = apps.get_model("inventory", "CompanyMember")
    InventoryAccess = apps.get_model("inventory", "InventoryAccess")
    KoperasiAccess = apps.get_model("koperasi", "KoperasiAccess")
    RiskAccess = apps.get_model("risk_management", "RiskAccess")

    for username, first_name, last_name, employee_id, division, position, archive_role in EMPLOYEES:
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": first_name, "last_name": last_name,
                "email": "it.pwujatim@gmail.com", "role": archive_role,
                "is_active": True, "password": make_password(username),
            },
        )
        updates = []
        for field, value in (("first_name", first_name), ("last_name", last_name)):
            if getattr(user, field) != value:
                setattr(user, field, value)
                updates.append(field)
        if not user.email:
            user.email = "it.pwujatim@gmail.com"
            updates.append("email")
        if updates:
            user.save(update_fields=updates)
        CompanyMember.objects.update_or_create(
            employee_id=employee_id,
            defaults={
                "user": user, "full_name": f"{first_name} {last_name}".strip(),
                "email": user.email, "division": division, "position": position,
                "status": "active",
            },
        )

    for user in User.objects.all():
        if not KoperasiAccess.objects.filter(user=user).exists():
            KoperasiAccess.objects.create(user=user, company=None, role="viewer", is_active=True)
        RiskAccess.objects.get_or_create(
            user=user,
            defaults={"role": "viewer", "division": None, "is_active": True},
        )
        InventoryAccess.objects.get_or_create(
            user=user,
            defaults={"role": "viewer", "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0013_add_employee_role"),
        ("inventory", "0001_initial"),
        ("koperasi", "0004_add_secretary_and_seed_organization_users"),
        ("risk_management", "0002_add_viewer_role"),
    ]
    operations = [
        migrations.AddField(
            model_name="companymember",
            name="user",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="company_member_profile", to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(seed_directory_and_access, migrations.RunPython.noop),
    ]
