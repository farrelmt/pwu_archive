from django.db import migrations


def clear_existing_emails(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    CompanyMember = apps.get_model("inventory", "CompanyMember")
    KoperasiMember = apps.get_model("koperasi", "Member")

    User.objects.exclude(email="").update(email="")
    CompanyMember.objects.exclude(email="").update(email="")
    KoperasiMember.objects.exclude(email="").update(email="")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0020_remove_placeholder_emails"),
    ]

    operations = [
        migrations.RunPython(clear_existing_emails, migrations.RunPython.noop),
    ]
