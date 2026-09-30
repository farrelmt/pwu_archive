from django.db import migrations


VALID_ROLES = {
    "chairman",
    "treasurer",
    "savings_treasurer",
    "business_treasurer",
    "member_section",
    "secretary",
    "supervisor",
    "admin",
    "manager",
    "finance",
    "officer",
    "auditor",
}


def remove_invalid_access_roles(apps, schema_editor):
    KoperasiAccess = apps.get_model("koperasi", "KoperasiAccess")
    KoperasiAccess.objects.exclude(role__in=VALID_ROLES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("koperasi", "0006_remove_default_viewer_access"),
        ("accounts", "0015_consolidate_risk_officers_and_kso_accounts"),
    ]

    operations = [
        migrations.RunPython(
            remove_invalid_access_roles,
            migrations.RunPython.noop,
        ),
    ]
