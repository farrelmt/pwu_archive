from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def has_monitor_access(user):
    return bool(user.is_authenticated and user.is_active)


def can_edit_assignment(user, assignment):
    return bool(has_monitor_access(user) and (
        user.is_superuser or user.role == "admin"
        or assignment.created_by_id == user.pk
        or assignment.responsible_id == user.pk
    ))


def monitor_required(view):
    @wraps(view)
    @login_required(login_url="accounts:login")
    def wrapped(request, *args, **kwargs):
        if not has_monitor_access(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped
