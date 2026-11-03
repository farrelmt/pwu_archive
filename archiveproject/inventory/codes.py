from uuid import uuid4


OWNERSHIP_PREFIXES = {
    "company": "COMPANY",
    "lumbung": "LUMBUNG",
    "personal": "PERSONAL",
    "third_party": "THIRD-PARTY",
}
LEGACY_PREFIXES = ("PRIBADI-", "INV-")


def asset_code_for_ownership(ownership, existing_code="", *, max_length=50):
    """Keep the identifier while making its ownership visible in the code."""
    prefix = OWNERSHIP_PREFIXES[ownership]
    code = (existing_code or "").strip()
    for old_prefix in (*LEGACY_PREFIXES, *(f"{value}-" for value in OWNERSHIP_PREFIXES.values())):
        if code.upper().startswith(old_prefix):
            code = code[len(old_prefix):]
            break
    suffix = code or uuid4().hex[:10].upper()
    return f"{prefix}-{suffix[:max_length - len(prefix) - 1]}"
