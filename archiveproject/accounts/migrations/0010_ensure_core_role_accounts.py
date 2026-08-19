from django.contrib.auth.hashers import make_password
from django.db import migrations


CORE_ACCOUNTS = (
    (
        "it_pwu",
        "admin",
        "IT",
        "PWU",
        "admin1234@",
        True,
        True,
    ),
    (
        "sekretaris",
        "sekretaris",
        "Sekretaris",
        "",
        "sekretaris",
        False,
        False,
    ),
    (
        "akuntan",
        "akuntan",
        "Akuntan",
        "",
        "akuntan",
        False,
        False,
    ),
)


def ensure_core_role_accounts(apps, schema_editor):
    SystemUser = apps.get_model("accounts", "SystemUser")

    for (
        username,
        role,
        first_name,
        last_name,
        initial_password,
        is_staff,
        is_superuser,
    ) in CORE_ACCOUNTS:
        user, created = SystemUser.objects.get_or_create(
            username=username,
            defaults={
                "role": role,
                "first_name": first_name,
                "last_name": last_name,
                "email": "it.pwujatim@gmail.com",
                "is_active": True,
                "is_staff": is_staff,
                "is_superuser": is_superuser,
                "password": make_password(initial_password),
            },
        )

        if created:
            continue

        update_fields = []
        if user.role != role:
            user.role = role
            update_fields.append("role")
        if not user.is_active:
            user.is_active = True
            update_fields.append("is_active")

        if username == "it_pwu":
            if not user.is_staff:
                user.is_staff = True
                update_fields.append("is_staff")
            if not user.is_superuser:
                user.is_superuser = True
                update_fields.append("is_superuser")

        if update_fields:
            user.save(update_fields=update_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0009_rename_spi_account"),
    ]

    operations = [
        migrations.RunPython(
            ensure_core_role_accounts,
            migrations.RunPython.noop,
        ),
    ]
