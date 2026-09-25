from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import InventoryAccess


WRITE_ROLES = {"manager", "officer"}


def access_for_user(user):
    if not user.is_authenticated or user.is_superuser:
        return None
    try:
        access = user.inventory_access
    except InventoryAccess.DoesNotExist:
        return None
    return access if access.is_active else None


def has_inventory_access(user):
    return bool(user.is_superuser or access_for_user(user))


def can_edit_inventory(user):
    if user.is_superuser:
        return True
    access = access_for_user(user)
    return bool(access and access.role in WRITE_ROLES)


def inventory_required(view_func):
    @login_required(login_url="accounts:login")
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not has_inventory_access(request.user):
            raise PermissionDenied("Anda tidak memiliki akses ke Sistem Inventaris.")
        request.inventory_access = access_for_user(request.user)
        request.can_edit_inventory = can_edit_inventory(request.user)
        return view_func(request, *args, **kwargs)
    return wrapped


def inventory_write_required(view_func):
    @inventory_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.can_edit_inventory:
            raise PermissionDenied("Akun Anda hanya memiliki akses baca.")
        return view_func(request, *args, **kwargs)
    return wrapped
