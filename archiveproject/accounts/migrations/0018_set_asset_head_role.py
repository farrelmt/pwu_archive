from django.db import migrations


def set_asset_head_role(apps, schema_editor):
    apps.get_model("accounts", "SystemUser").objects.filter(
        username="aset_0"
    ).update(role="kadiv_aset")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0017_merge_accounts_and_reorder_assets"),
    ]

    operations = [
        migrations.RunPython(set_asset_head_role, migrations.RunPython.noop),
    ]
