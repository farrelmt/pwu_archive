from django.contrib.auth.hashers import make_password
from django.db import migrations, models


def create_wirajatim_kso_user(apps, schema_editor):
    SystemUser = apps.get_model('accounts', 'SystemUser')
    SystemUser.objects.filter(username='kadiv_spi').update(
        first_name='Kepala',
        last_name='SPI',
    )
    SystemUser.objects.get_or_create(
        username='wirajatim_kso',
        defaults={
            'password': make_password('wirajatim_kso'),
            'role': 'wirajatim_kso',
            'first_name': 'Wirajatim',
            'last_name': 'KSO',
            'email': 'it.pwujatim@gmail.com',
            'is_active': True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0007_alter_systemuser_role'),
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
                    ('kadiv_spi', 'Kepala SPI'),
                    ('akuntan', 'Akuntan'),
                    ('wirajatim_kso', 'Wirajatim KSO'),
                ],
                max_length=30,
            ),
        ),
        migrations.RunPython(
            create_wirajatim_kso_user,
            migrations.RunPython.noop,
        ),
    ]
