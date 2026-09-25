from django.contrib.auth.hashers import make_password
from django.db import migrations


def consolidate_accounts(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    KoperasiAccess = apps.get_model("koperasi", "KoperasiAccess")
    RiskAccess = apps.get_model("risk_management", "RiskAccess")
    InventoryAccess = apps.get_model("inventory", "InventoryAccess")

    # Risk Officer remains an assignable RiskAccess role. The standalone seed
    # identities are removed so that the role can be attached to a real shared
    # employee account instead.
    User.objects.filter(username__in=[f"risk_officer_{i}" for i in range(1, 10)]).delete()

    original = User.objects.filter(username="wirajatim_kso").first()
    if original is not None:
        original.username = "wirajatim_kso_0"
        original.first_name = "Wirajatim KSO 0"
        original.last_name = ""
        original.password = make_password("wirajatim_kso_0")
        original.save(update_fields=["username", "first_name", "last_name", "password"])

    for number in range(6):
        username = f"wirajatim_kso_{number}"
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": f"Wirajatim KSO {number}",
                "last_name": "",
                "email": "it.pwujatim@gmail.com",
                "role": "wirajatim_kso",
                "is_active": True,
                "password": make_password(username),
            },
        )
        if created:
            KoperasiAccess.objects.get_or_create(
                user=user,
                company=None,
                defaults={"role": "viewer", "is_active": True},
            )
            RiskAccess.objects.get_or_create(
                user=user,
                defaults={"role": "viewer", "division": None, "is_active": True},
            )
            InventoryAccess.objects.get_or_create(
                user=user,
                defaults={"role": "viewer", "is_active": True},
            )


def restore_accounts(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    RiskAccess = apps.get_model("risk_management", "RiskAccess")
    RiskDivision = apps.get_model("risk_management", "RiskDivision")

    User.objects.filter(username__in=[f"wirajatim_kso_{i}" for i in range(1, 6)]).delete()
    original = User.objects.filter(username="wirajatim_kso_0").first()
    if original is not None:
        original.username = "wirajatim_kso"
        original.first_name = "Wirajatim"
        original.last_name = "KSO"
        original.password = make_password("wirajatim_kso")
        original.save(update_fields=["username", "first_name", "last_name", "password"])

    divisions = list(RiskDivision.objects.order_by("pk")[:9])
    for number, division in enumerate(divisions, start=1):
        username = f"risk_officer_{number}"
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": "Risk Officer",
                "last_name": division.name,
                "email": "it.pwujatim@gmail.com",
                "role": "risk",
                "is_active": True,
                "password": make_password(username),
            },
        )
        RiskAccess.objects.update_or_create(
            user=user,
            defaults={"role": "risk_officer", "division": division, "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0014_replace_person_usernames"),
        ("inventory", "0002_shared_accounts_and_company_members"),
        ("koperasi", "0004_add_secretary_and_seed_organization_users"),
        ("risk_management", "0003_riskmonitoring_riskactionplan"),
    ]

    operations = [
        migrations.RunPython(consolidate_accounts, restore_accounts),
    ]
