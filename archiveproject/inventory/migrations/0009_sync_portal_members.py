from django.db import migrations


def member_division(username):
    username = (username or "").casefold()
    groups = (
        (("akuntansi_",), "Divisi Akuntansi"),
        (("aset_",), "Divisi Aset"),
        (("keuangan_",), "Divisi Keuangan"),
        (("legal_", "legal_umum_"), "Divisi Legal dan Umum"),
        (("manajemen_risiko_",), "Divisi Manajemen Risiko"),
        (("sekretaris_",), "Divisi Sekretaris"),
        (("spi_",), "Divisi Satuan Pengawas Internal"),
        (("umum_",), "Divisi Umum"),
        (("humas_",), "Humas"),
        (("hrd_",), "HRD"),
        (("wirajatim_kso_",), "Wirajatim KSO"),
    )
    if username in {"direktur", "direktur_utama"}:
        return "Direksi"
    if username in {"it_pwu", "farrel_mt"}:
        return "Administrator Sistem"
    for prefixes, division in groups:
        if username.startswith(prefixes):
            return division
    return "Lainnya"


def sync_portal_members(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    CompanyMember = apps.get_model("inventory", "CompanyMember")
    role_labels = dict(User._meta.get_field("role").choices)

    for user in User.objects.all():
        full_name = f"{user.first_name} {user.last_name}".strip() or user.username
        base_id = f"PWU-{user.pk:04d}"
        employee_id = base_id
        suffix = 1
        while CompanyMember.objects.filter(employee_id=employee_id).exclude(user_id=user.pk).exists():
            suffix += 1
            employee_id = f"{base_id}-{suffix}"
        defaults = {
            "employee_id": employee_id,
            "full_name": full_name,
            "email": user.email or "",
            "phone": user.phone or "",
            "division": member_division(user.username),
            "position": role_labels.get(user.role) or "Pegawai",
            "status": "active" if user.is_active else "inactive",
        }
        member, _ = CompanyMember.objects.get_or_create(user_id=user.pk, defaults=defaults)
        for field in ("full_name", "email", "phone", "division", "position", "status"):
            setattr(member, field, defaults[field])
        member.save()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0021_clear_existing_emails"),
        ("inventory", "0008_separate_laptop_category"),
    ]

    operations = [
        migrations.RunPython(sync_portal_members, migrations.RunPython.noop),
    ]
