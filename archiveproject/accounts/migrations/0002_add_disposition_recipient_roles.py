from django.contrib.auth.hashers import make_password
from django.db import migrations, models


ROLE_ACCOUNTS = (
    ('dirut', 'direktur_utama', 'Direktur', 'Utama'),
    ('direktur_umum', 'direktur_umum', 'Direktur', 'Umum'),
    ('kadiv_akuntansi', 'kadiv_akuntansi', 'Kepala Divisi', 'Akuntansi'),
    ('kadiv_keuangan', 'kadiv_keuangan', 'Kepala Divisi', 'Keuangan'),
    ('kadiv_risiko', 'kadiv_risiko', 'Kepala Divisi', 'Manajemen Risiko'),
    ('kadiv_legal_umum', 'kadiv_legal_umum', 'Kepala Divisi', 'Legal dan Umum'),
    ('kadiv_aset', 'kadiv_aset', 'Kepala Divisi', 'Aset'),
    ('kadiv_spi', 'kadiv_spi', 'Kepala Divisi', 'SPI'),
)


def ensure_role_accounts(apps, schema_editor):
    SystemUser = apps.get_model('accounts', 'SystemUser')
    for username, role, first_name, last_name in ROLE_ACCOUNTS:
        user, created = SystemUser.objects.get_or_create(
            username=username,
            defaults={
                'role': role,
                'first_name': first_name,
                'last_name': last_name,
                'is_active': True,
                'password': make_password(None),
            },
        )
        if not created and not user.role:
            user.role = role
            update_fields = ['role']
            if not user.first_name:
                user.first_name = first_name
                update_fields.append('first_name')
            if not user.last_name:
                user.last_name = last_name
                update_fields.append('last_name')
            user.save(update_fields=update_fields)


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemuser',
            name='role',
            field=models.CharField(
                choices=[
                    ('admin', 'Admin'),
                    ('sekretaris', 'Sekretaris'),
                    ('kadiv', 'Kepala Divisi'),
                    ('direktur', 'Direktur'),
                    ('direktur_utama', 'Direktur Utama'),
                    ('direktur_umum', 'Direktur Umum'),
                    ('kadiv_akuntansi', 'Kepala Divisi Akuntansi'),
                    ('kadiv_keuangan', 'Kepala Divisi Keuangan'),
                    ('kadiv_risiko', 'Kepala Divisi Manajemen Risiko'),
                    ('kadiv_legal_umum', 'Kepala Divisi Legal dan Umum'),
                    ('kadiv_aset', 'Kepala Divisi Aset'),
                    ('kadiv_spi', 'Kepala Divisi SPI'),
                ],
                max_length=30,
            ),
        ),
        migrations.RunPython(ensure_role_accounts, migrations.RunPython.noop),
    ]
