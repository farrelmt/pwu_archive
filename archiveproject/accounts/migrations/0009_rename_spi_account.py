from django.contrib.auth.hashers import make_password
from django.db import migrations


def rename_spi_account(apps, schema_editor):
    SystemUser = apps.get_model('accounts', 'SystemUser')
    SystemUser.objects.filter(
        username='kadiv_spi',
        role='kadiv_spi',
    ).update(
        username='ka_spi',
        password=make_password('ka_spi'),
    )


def restore_spi_account(apps, schema_editor):
    SystemUser = apps.get_model('accounts', 'SystemUser')
    SystemUser.objects.filter(
        username='ka_spi',
        role='kadiv_spi',
    ).update(
        username='kadiv_spi',
        password=make_password('kadiv_spi'),
    )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0008_add_wirajatim_kso_role_user'),
    ]

    operations = [
        migrations.RunPython(rename_spi_account, restore_spi_account),
    ]
