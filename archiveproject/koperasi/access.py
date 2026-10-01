from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Company, KoperasiAccess


WRITE_ROLES = {
    "admin",
    "manager",
    "chairman",
    "finance",
    "officer",
    "treasurer",
    "savings_treasurer",
    "business_treasurer",
    "member_section",
    "secretary",
}
MANAGE_ROLES = {
    "admin",
    "manager",
    "chairman",
    "treasurer",
    "savings_treasurer",
    "business_treasurer",
}
APPROVE_ROLES = {
    "admin",
    "manager",
    "chairman",
    "savings_treasurer",
    "business_treasurer",
}
VALID_ROLES = frozenset(value for value, _label in KoperasiAccess.ROLE_CHOICES)


def access_rows_for_user(user):
    if not user.is_authenticated:
        return KoperasiAccess.objects.none()
    return KoperasiAccess.objects.filter(
        user=user,
        is_active=True,
        role__in=VALID_ROLES,
    )


def _cached_access_rows(user):
    if user.is_superuser:
        return ()
    cached = user.__dict__.get("_koperasi_access_rows_cache")
    if cached is None:
        cached = tuple(access_rows_for_user(user).select_related("company"))
        user.__dict__["_koperasi_access_rows_cache"] = cached
    return cached


def accessible_companies(user):
    if user.is_superuser:
        return Company.objects.all()
    rows = _cached_access_rows(user)
    if not rows or any(row.company_id is None for row in rows):
        return Company.objects.all()
    return Company.objects.filter(pk__in={row.company_id for row in rows})


def roles_for_user(user):
    if user.is_superuser:
        return {"admin"}
    cached = user.__dict__.get("_koperasi_roles_cache")
    if cached is not None:
        return cached
    roles = {row.role for row in _cached_access_rows(user)}
    user.__dict__["_koperasi_roles_cache"] = roles
    return roles


def can_manage_global_access(user):
    if user.is_superuser:
        return True
    return any(
        row.company_id is None and row.role in MANAGE_ROLES
        for row in _cached_access_rows(user)
    )


def koperasi_required(view_func):
    @login_required(login_url="accounts:login")
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        roles = roles_for_user(request.user)
        if not roles:
            raise PermissionDenied("Anda tidak memiliki akses ke Sistem Koperasi.")
        request.koperasi_roles = roles
        request.koperasi_companies = accessible_companies(request.user)
        return view_func(request, *args, **kwargs)

    return wrapped


def koperasi_write_required(view_func):
    @koperasi_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.koperasi_roles.intersection(WRITE_ROLES):
            raise PermissionDenied("Akun Anda hanya memiliki akses baca.")
        return view_func(request, *args, **kwargs)

    return wrapped


def koperasi_manage_required(view_func):
    @koperasi_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.koperasi_roles.intersection(MANAGE_ROLES):
            raise PermissionDenied("Tindakan ini membutuhkan akses manajer.")
        return view_func(request, *args, **kwargs)

    return wrapped


def koperasi_admin_required(view_func):
    @koperasi_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not can_manage_global_access(request.user):
            raise PermissionDenied(
                "Tindakan ini membutuhkan akses administrator Koperasi Grup."
            )
        return view_func(request, *args, **kwargs)

    return wrapped
