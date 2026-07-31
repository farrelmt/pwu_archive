from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.urls import reverse

from accounts.audit import record_activity


def send_disposition_shared_notifications(*, request, disposisi, recipient_roles):
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

    for user in users:
        subject = f'NOTIFIKASI SISTEM ARSIP - {disposisi.nomor_agenda}'
        body = (
            f'Yth. {user.get_full_name() or user.username},\n\n'
            f'Disposisi {disposisi.nomor_agenda} telah dibagikan kepada Anda.\n'
            f'Nomor surat: {disposisi.nomor_surat}\n'
            f'Perihal: {disposisi.perihal}\n\n'
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
                request=request,
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
                request=request,
                category='SYSTEM',
                action='DISPOSITION_EMAIL_SENT',
                description='Disposition notification email sent.',
                target_type='disposisi.Disposisi',
                target_id=disposisi.pk,
                target_label=disposisi.nomor_agenda or disposisi.nomor_surat,
                metadata={'recipient': user.username},
            )

    return sent_count, failed_count
