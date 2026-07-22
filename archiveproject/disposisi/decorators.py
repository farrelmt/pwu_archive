from functools import wraps

from django.core.exceptions import PermissionDenied


def disposisi_editor_required(view_func):
    """Allow disposition mutations only for configured editors."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if request.user.can_edit_disposisi:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied

    return wrapped


def disposisi_director_required(view_func):
    """Allow online disposition decisions only for directors."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if request.user.can_approve_disposisi:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied

    return wrapped
