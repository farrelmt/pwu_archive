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


def can_manage_inventory(user):
    if user.is_superuser:
        return True
    access = access_for_user(user)
    return bool(access and access.role == "manager")


def pic_division(user):
    access = access_for_user(user)
    return access.division if access and access.role == "division_pic" and access.division else None


def can_write_inventory(user):
    return can_edit_inventory(user) or bool(pic_division(user))


def can_access_member(user, member):
    return (can_edit_inventory(user) or member.user_id == user.pk
            or bool(pic_division(user) and member.division == pic_division(user)))


def can_write_item(user, item):
    return can_edit_inventory(user) or bool(
        item.assigned_to_id and pic_division(user)
        and item.assigned_to.division == pic_division(user)
    )


def can_view_internet(user):
    return bool(user.is_authenticated and user.is_active and (
        can_manage_inventory(user) or user.username == "it_pwu"
    ))


def inventory_required(view_func):
    @login_required(login_url="accounts:login")
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not has_inventory_access(request.user):
            raise PermissionDenied("Anda tidak memiliki akses ke Sistem Inventaris.")
        request.inventory_access = access_for_user(request.user)
        request.can_edit_inventory = can_edit_inventory(request.user)
        request.pic_division = pic_division(request.user)
        request.can_write_inventory = can_write_inventory(request.user)
        request.can_manage_inventory = can_manage_inventory(request.user)
        request.can_view_internet = can_view_internet(request.user)
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
