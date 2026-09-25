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


def access_rows_for_user(user):
    if not user.is_authenticated:
        return KoperasiAccess.objects.none()
    return KoperasiAccess.objects.filter(user=user, is_active=True)


def accessible_companies(user):
    if user.is_superuser:
        return Company.objects.all()
    rows = access_rows_for_user(user)
    if not rows.exists() or rows.filter(company__isnull=True).exists():
        return Company.objects.all()
    return Company.objects.filter(accesses__in=rows).distinct()


def roles_for_user(user):
    if user.is_superuser:
        return {"admin"}
    roles = set(access_rows_for_user(user).values_list("role", flat=True))
    return roles


def can_manage_global_access(user):
    if user.is_superuser:
        return True
    return access_rows_for_user(user).filter(
        company__isnull=True,
        role__in=MANAGE_ROLES,
    ).exists()


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
