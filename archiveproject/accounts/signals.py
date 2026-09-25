from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db import transaction

from .audit import record_activity
from .models import SystemUser


@receiver(post_save, sender=SystemUser)
def ensure_shared_system_access(sender, instance, created, **kwargs):
    """Every active PWU identity participates in the Inventory system."""
    if not created:
        return
    user_pk = instance.pk

    def create_baseline_access():
        from inventory.models import InventoryAccess
        InventoryAccess.objects.get_or_create(
            user_id=user_pk,
            defaults={"role": "participant", "is_active": True},
        )

    transaction.on_commit(create_baseline_access)


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
