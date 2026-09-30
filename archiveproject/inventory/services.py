from accounts.directory import member_division

from .models import CompanyMember


def _available_employee_id(user):
    base = f"PWU-{user.pk:04d}"
    candidate = base
    suffix = 1
    while CompanyMember.objects.filter(employee_id=candidate).exclude(user=user).exists():
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def sync_company_member(user):
    """Create or synchronize the Inventory profile for a portal member."""
    defaults = {
        "employee_id": _available_employee_id(user),
        "full_name": user.get_full_name().strip() or user.username,
        "email": user.email or "",
        "phone": user.phone or "",
        "division": member_division(user.username),
        "position": user.get_role_display() or "Pegawai",
        "status": "active" if user.is_active else "inactive",
    }
    member, created = CompanyMember.objects.get_or_create(user=user, defaults=defaults)
    if created:
        return member

    changed_fields = []
    for field in ("full_name", "email", "phone", "division", "position", "status"):
        value = defaults[field]
        if getattr(member, field) != value:
            setattr(member, field, value)
            changed_fields.append(field)
    if changed_fields:
        member.save(update_fields=[*changed_fields, "updated_at"])
    return member
