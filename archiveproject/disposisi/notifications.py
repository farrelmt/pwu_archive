from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.urls import reverse

from accounts.audit import record_activity
from .models import Disposisi


def deliver_disposition_shared_notifications(
    *,
    disposisi_id,
    recipient_roles,
    actor_id=None,
    actor_username='',
):
    disposisi = Disposisi.objects.get(pk=disposisi_id)
    actor = None
    if actor_id:
        actor = get_user_model().objects.filter(pk=actor_id).first()
    users = get_user_model().objects.filter(
        is_active=True,
        role__in=recipient_roles,
    ).order_by('pk')
    detail_url = (
        f"{settings.SYSTEM_BASE_URL}"
        f"{reverse('disposisi:detaildisposisi', args=[disposisi.pk])}"
    )
    sent_count = 0
    failed_count = 0
    deadline_line = (
        f'Deadline: {disposisi.deadline:%d/%m/%Y}\n\n'
        if disposisi.deadline
        else ''
    )

    for user in users:
        if not (user.email or '').strip():
            continue
        subject = f'NOTIFIKASI SISTEM ARSIP - {disposisi.nomor_agenda}'
        body = (
            f'Yth. {user.get_full_name() or user.username},\n\n'
            f'Disposisi {disposisi.nomor_agenda} telah dibagikan kepada Anda.\n'
            f'Nomor surat: {disposisi.nomor_surat}\n'
            f'Perihal: {disposisi.perihal}\n\n'
            f'{deadline_line}'
            f'Buka disposisi: {detail_url}\n'
        )
        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception as exc:
            failed_count += 1
            record_activity(
                actor=actor,
                actor_username=actor_username,
                category='SYSTEM',
                action='DISPOSITION_EMAIL_FAILED',
                description='Disposition notification email failed.',
                target_type='disposisi.Disposisi',
                target_id=disposisi.pk,
                target_label=disposisi.nomor_agenda or disposisi.nomor_surat,
                metadata={
                    'recipient': user.username,
                    'error_type': type(exc).__name__,
                },
                success=False,
            )
        else:
            sent_count += 1
            record_activity(
                actor=actor,
                actor_username=actor_username,
                category='SYSTEM',
                action='DISPOSITION_EMAIL_SENT',
                description='Disposition notification email sent.',
                target_type='disposisi.Disposisi',
                target_id=disposisi.pk,
                target_label=disposisi.nomor_agenda or disposisi.nomor_surat,
                metadata={'recipient': user.username},
            )

    return sent_count, failed_count


def send_disposition_shared_notifications(*, request, disposisi, recipient_roles):
    """Queue disposition email delivery and return without waiting for SMTP."""
    recipient_roles = sorted(set(recipient_roles))
    queued_count = get_user_model().objects.filter(
        is_active=True,
        role__in=recipient_roles,
    ).exclude(email='').count()
    if not queued_count:
        return 0, 0

    from .tasks import send_disposition_shared_notifications_task

    try:
        send_disposition_shared_notifications_task.delay(
            disposisi.pk,
            recipient_roles,
            request.user.pk,
            request.user.get_username(),
        )
    except Exception as exc:
        record_activity(
            request=request,
            category='SYSTEM',
            action='DISPOSITION_EMAIL_QUEUE_FAILED',
            description='Disposition notification could not be queued.',
            target_type='disposisi.Disposisi',
            target_id=disposisi.pk,
            target_label=disposisi.nomor_agenda or disposisi.nomor_surat,
            metadata={'error_type': type(exc).__name__},
            success=False,
        )
        return 0, queued_count
    return queued_count, 0
