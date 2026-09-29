from django.db import migrations


PLACEHOLDER_EMAIL = "it.pwujatim@gmail.com"


def clear_placeholder_emails(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    CompanyMember = apps.get_model("inventory", "CompanyMember")
    KoperasiMember = apps.get_model("koperasi", "Member")

    User.objects.filter(email__iexact=PLACEHOLDER_EMAIL).update(email="")
    CompanyMember.objects.filter(email__iexact=PLACEHOLDER_EMAIL).update(email="")
    KoperasiMember.objects.filter(email__iexact=PLACEHOLDER_EMAIL).update(email="")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0019_rename_secretary_accounts_to_humas_hrd"),
        ("inventory", "0004_expand_it_asset_categories"),
        ("koperasi", "0006_remove_default_viewer_access"),
    ]

    operations = [
        migrations.RunPython(clear_placeholder_emails, migrations.RunPython.noop),
    ]
