from django.contrib.auth.hashers import make_password
from django.db import migrations


def apply_changes(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    DisposisiLog = apps.get_model("disposisi", "DisposisiLog")

    alzira = User.objects.filter(username="sekretaris_0").first()
    old_secretary = User.objects.filter(username="sekretaris").first()
    if alzira is not None:
        alzira.role = "sekretaris"
        alzira.save(update_fields=["role"])
        if old_secretary is not None:
            DisposisiLog.objects.filter(user_log=old_secretary).update(user_log=alzira)
            old_secretary.delete()

    User.objects.filter(username="akuntan").delete()

    User.objects.filter(username__in=["umum_0", "umum_1"]).update(
        first_name="",
        last_name="",
        role="",
    )

    asset_changes = {
        "aset_0": ("__asset_swap_arya", "aset_1"),
        "aset_1": ("__asset_swap_ryan", "aset_2"),
        "aset_2": ("__asset_swap_eddy", "aset_0"),
    }
    staged = []
    for old_username, (temporary_username, new_username) in asset_changes.items():
        user = User.objects.filter(username=old_username).first()
        if user is None:
            continue
        user.username = temporary_username
        user.save(update_fields=["username"])
        staged.append((user.pk, new_username))
    for user_id, new_username in staged:
        user = User.objects.get(pk=user_id)
        user.username = new_username
        user.password = make_password(new_username)
        user.save(update_fields=["username", "password"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0016_remove_functional_dummy_accounts"),
        ("disposisi", "0032_disposisi_dual_director_content"),
    ]

    operations = [
        migrations.RunPython(apply_changes, migrations.RunPython.noop),
    ]
