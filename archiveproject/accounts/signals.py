from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .audit import record_activity


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    record_activity(
        request=request,
        actor=user,
        category='AUTH',
        action='LOGIN',
        description='User logged in.',
    )


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    record_activity(
        request=request,
        actor=user,
        actor_username=user.get_username() if user is not None else '',
        category='AUTH',
        action='LOGOUT',
        description='User logged out.',
    )


@receiver(user_login_failed)
def audit_login_failed(sender, credentials, request, **kwargs):
    record_activity(
        request=request,
        actor_username=str(credentials.get('username', '')),
        category='AUTH',
        action='LOGIN_FAILED',
        description='Login attempt failed.',
        success=False,
    )
