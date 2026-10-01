from celery import shared_task

from .notifications import deliver_disposition_shared_notifications


@shared_task
def send_disposition_shared_notifications_task(
    disposisi_id,
    recipient_roles,
    actor_id=None,
    actor_username='',
):
    return deliver_disposition_shared_notifications(
        disposisi_id=disposisi_id,
        recipient_roles=recipient_roles,
        actor_id=actor_id,
        actor_username=actor_username,
    )
