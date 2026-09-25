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
    if system == "archive":
        return has_archive_access(user)
    if system == "koperasi":
        return user.koperasi_accesses.filter(is_active=True).exists()
    if system == "risk":
        return user.risk_accesses.filter(is_active=True).exists()
    if system == "inventory":
        try:
            return user.inventory_access.is_active
        except ObjectDoesNotExist:
            return False
    return False


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
