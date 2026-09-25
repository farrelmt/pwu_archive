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


def roles_for_user(user):
    if user.is_superuser:
        return {"head_manager"}
    return set(accesses_for_user(user).values_list("role", flat=True))


def has_risk_access(user):
    return bool(user.is_superuser or accesses_for_user(user).exists())


def risks_for_user(user):
    queryset = RiskRegister.objects.select_related("division", "created_by", "updated_by")
    if user.is_superuser:
        return queryset
    accesses = accesses_for_user(user)
    if not accesses.exists():
        return queryset.none()
    if accesses.filter(role__in=MANAGER_ROLES).exists():
        return queryset
    division_ids = accesses.exclude(division__isnull=True).values_list("division_id", flat=True)
    return queryset.filter(division_id__in=division_ids).distinct()


def can_edit_risks(user):
    if user.is_superuser:
        return True
    return accesses_for_user(user).filter(role__in=EDITOR_ROLES).exists()


def can_edit_risk(user, risk):
    if user.is_superuser:
        return True
    accesses = accesses_for_user(user).filter(role__in=EDITOR_ROLES)
    if not accesses.exists():
        return False
    return (
        accesses.filter(role__in=MANAGER_ROLES).exists()
        or accesses.filter(division_id=risk.division_id).exists()
    )


def risk_required(view_func):
    @login_required(login_url="accounts:login")
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not has_risk_access(request.user):
            raise PermissionDenied("Anda tidak memiliki akses ke Sistem Manajemen Risiko.")
        request.risk_accesses = accesses_for_user(request.user)
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
