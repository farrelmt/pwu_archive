from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import RiskAccess, RiskRegister


MANAGER_ROLES = {"head_manager", "manager_member"}
EDITOR_ROLES = MANAGER_ROLES | {"risk_officer"}


def accesses_for_user(user):
    if not user.is_authenticated or user.is_superuser:
        return RiskAccess.objects.none()
    return RiskAccess.objects.filter(user=user, is_active=True).select_related("division")


def _cached_access_rows(user):
    if user.is_superuser:
        return ()
    cached = user.__dict__.get("_risk_access_rows_cache")
    if cached is None:
        cached = tuple(accesses_for_user(user))
        user.__dict__["_risk_access_rows_cache"] = cached
    return cached


def roles_for_user(user):
    if user.is_superuser:
        return {"head_manager"}
    cached = user.__dict__.get("_risk_roles_cache")
    if cached is not None:
        return cached
    roles = {access.role for access in _cached_access_rows(user)}
    user.__dict__["_risk_roles_cache"] = roles
    return roles


def has_risk_access(user):
    return bool(user.is_superuser or roles_for_user(user))


def risks_for_user(user):
    queryset = RiskRegister.objects.select_related("division", "created_by", "updated_by")
    if user.is_superuser:
        return queryset
    accesses = _cached_access_rows(user)
    if not accesses:
        return queryset.none()
    if any(access.role in MANAGER_ROLES for access in accesses):
        return queryset
    division_ids = {
        access.division_id for access in accesses
        if access.division_id is not None
    }
    return queryset.filter(division_id__in=division_ids).distinct()


def can_edit_risks(user):
    if user.is_superuser:
        return True
    return bool(roles_for_user(user).intersection(EDITOR_ROLES))


def can_edit_risk(user, risk):
    if user.is_superuser:
        return True
    accesses = [
        access for access in _cached_access_rows(user)
        if access.role in EDITOR_ROLES
    ]
    if not accesses:
        return False
    return (
        any(access.role in MANAGER_ROLES for access in accesses)
        or any(access.division_id == risk.division_id for access in accesses)
    )


def risk_required(view_func):
    @login_required(login_url="accounts:login")
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not has_risk_access(request.user):
            raise PermissionDenied("Anda tidak memiliki akses ke Sistem Manajemen Risiko.")
        request.risk_accesses = _cached_access_rows(request.user)
        request.risk_role_display = ", ".join(
            access.get_role_display() for access in request.risk_accesses
        )
        request.can_edit_risks = can_edit_risks(request.user)
        return view_func(request, *args, **kwargs)

    return wrapped


def risk_write_required(view_func):
    @risk_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.can_edit_risks:
            raise PermissionDenied("Akun Kepala Divisi hanya memiliki akses baca.")
        return view_func(request, *args, **kwargs)

    return wrapped
