from django.db import migrations


USERNAME_CHANGES = (
    ('dirut', 'direktur_utama'),
    ('direktur_umum', 'direktur'),
)


def rename_director_usernames(apps, schema_editor):
    SystemUser = apps.get_model('accounts', 'SystemUser')
    for old_username, new_username in USERNAME_CHANGES:
        user = SystemUser.objects.filter(username=old_username).first()
        if user is None:
            continue
        if SystemUser.objects.filter(username=new_username).exists():
            raise RuntimeError(
                f'Username tujuan sudah digunakan: {new_username}'
            )
        user.username = new_username
        user.save(update_fields=['username'])


def restore_director_usernames(apps, schema_editor):
    SystemUser = apps.get_model('accounts', 'SystemUser')
    for old_username, new_username in reversed(USERNAME_CHANGES):
        user = SystemUser.objects.filter(username=new_username).first()
        if user is None:
            continue
        if SystemUser.objects.filter(username=old_username).exists():
            raise RuntimeError(
                f'Username asal sudah digunakan: {old_username}'
            )
        user.username = old_username
        user.save(update_fields=['username'])


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_add_disposition_recipient_roles'),
    ]

    operations = [
        migrations.RunPython(
            rename_director_usernames,
            restore_director_usernames,
        ),
    ]
