from uuid import uuid4

from django.db import migrations


PREFIXES = {
    "company": "COMPANY",
    "lumbung": "LUMBUNG",
    "personal": "PERSONAL",
    "third_party": "THIRD-PARTY",
}


def update_asset_codes(apps, schema_editor):
    InventoryItem = apps.get_model("inventory", "InventoryItem")
    items = list(InventoryItem.objects.order_by("pk").values_list("pk", "asset_code", "ownership"))
    changes = []
    used = set()
    known_prefixes = ("PRIBADI-", "INV-", *(f"{prefix}-" for prefix in PREFIXES.values()))
    for pk, old_code, ownership in items:
        prefix = PREFIXES.get(ownership, "COMPANY")
        suffix = (old_code or "").strip()
        for known in known_prefixes:
            if suffix.upper().startswith(known):
                suffix = suffix[len(known):]
                break
        suffix = suffix or str(pk)
        code = f"{prefix}-{suffix[:50 - len(prefix) - 1]}"
        if code in used:
            discriminator = f"-{pk}"
            code = f"{prefix}-{suffix[:50 - len(prefix) - len(discriminator) - 1]}{discriminator}"
        used.add(code)
        changes.append((pk, code))

    # Temporary unique values prevent a collision when two old codes exchange prefixes.
    old_codes = {code for _, code, _ in items}
    temporary_codes = set()
    for pk, _ in changes:
        temporary = f"TMP-CODE-{pk}"
        while temporary in old_codes or temporary in temporary_codes:
            temporary = f"TMP-CODE-{uuid4().hex[:20]}"
        temporary_codes.add(temporary)
        InventoryItem.objects.filter(pk=pk).update(asset_code=temporary)
    for pk, code in changes:
        InventoryItem.objects.filter(pk=pk).update(asset_code=code)


class Migration(migrations.Migration):
    dependencies = [("inventory", "0010_inventory_item_ownership")]

    operations = [
        migrations.RunPython(update_asset_codes, migrations.RunPython.noop),
    ]
