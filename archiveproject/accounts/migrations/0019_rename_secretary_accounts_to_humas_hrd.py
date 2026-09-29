from django.contrib.auth.hashers import make_password
from django.db import migrations


USERNAME_CHANGES = {
    "sekretaris_1": "humas_0",
    "sekretaris_2": "hrd_0",
}


def rename_accounts(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    for old_username, new_username in USERNAME_CHANGES.items():
        user = User.objects.filter(username=old_username).first()
        if user is None:
            continue
        if User.objects.filter(username=new_username).exclude(pk=user.pk).exists():
            raise RuntimeError(f"Username tujuan sudah digunakan: {new_username}")
        user.username = new_username
        user.password = make_password(new_username)
        user.save(update_fields=["username", "password"])


def restore_accounts(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    for old_username, new_username in reversed(tuple(USERNAME_CHANGES.items())):
        user = User.objects.filter(username=new_username).first()
        if user is None:
            continue
        if User.objects.filter(username=old_username).exclude(pk=user.pk).exists():
            raise RuntimeError(f"Username lama sudah digunakan: {old_username}")
        user.username = old_username
        user.password = make_password(old_username)
        user.save(update_fields=["username", "password"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0018_set_asset_head_role"),
    ]

    operations = [
        migrations.RunPython(rename_accounts, restore_accounts),
    ]
