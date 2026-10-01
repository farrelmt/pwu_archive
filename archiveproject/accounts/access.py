from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied


MEMBER_ADMIN_USERNAMES = {"it_pwu", "farrel_mt"}

ARCHIVE_ACCESS_ROLES = {
    "admin",
    "sekretaris",
    "kadiv",
    "direktur",
    "direktur_utama",
    "direktur_umum",
    "kadiv_akuntansi",
    "kadiv_keuangan",
    "kadiv_risiko",
    "kadiv_legal_umum",
    "kadiv_aset",
    "kadiv_spi",
    "akuntan",
    "wirajatim_kso",
}


def has_archive_access(user):
    return bool(
        user.is_authenticated
        and user.is_active
        and (user.is_superuser or user.role in ARCHIVE_ACCESS_ROLES)
    )


def has_system_access(user, system):
    """Return whether an account has an active role in the requested system."""
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    cache = user.__dict__.setdefault("_pwu_system_access_cache", {})
    if system in cache:
        return cache[system]
    if system == "archive":
        allowed = has_archive_access(user)
    elif system == "koperasi":
        from koperasi.access import roles_for_user

        allowed = bool(roles_for_user(user))
    elif system == "risk":
        from risk_management.access import has_risk_access

        allowed = has_risk_access(user)
    elif system == "inventory":
        try:
            allowed = user.inventory_access.is_active
        except ObjectDoesNotExist:
            allowed = False
    else:
        allowed = False
    cache[system] = allowed
    return allowed


def can_manage_members(user):
    return bool(
        user.is_authenticated
        and (
            user.is_superuser
            or user.role == "admin"
            or user.username in MEMBER_ADMIN_USERNAMES
        )
    )


def member_admin_required(view_func):
    @wraps(view_func)
    @login_required(login_url="accounts:login")
    def wrapped(request, *args, **kwargs):
        if not can_manage_members(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped
