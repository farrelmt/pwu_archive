from django.db.models import Q

from disposisi.models import Disposisi


PROCESSED_STATUSES = [
    'DIAJUKAN', 'DIISI', 'DIBAGIKAN', 'VERIFIKASI', 'SELESAI',
]
SHARED_STATUSES = ['DIBAGIKAN', 'VERIFIKASI', 'SELESAI']


def inbox_disposisi_for_user(user):
    """Return documents on which the current user needs to take action."""
    if not user.is_authenticated:
        return Disposisi.objects.none()

    filters = Q()
    if user.is_superuser:
        filters |= Q(
            status_pengajuan__in=[
                'DIAJUKAN', 'DIISI', 'DIBAGIKAN', 'VERIFIKASI',
            ]
        )
    else:
        if user.role == 'direktur_utama':
            filters |= Q(
                status_pengajuan='DIAJUKAN',
                tujuan__in=['DIRUT', 'DIREKSI'],
            )
        elif user.role in {'direktur', 'direktur_umum'}:
            filters |= Q(
                status_pengajuan='DIAJUKAN',
                tujuan__in=['DIR', 'DIREKSI'],
            )

        if user.role == 'sekretaris':
            filters |= Q(status_pengajuan__in=['DIISI', 'VERIFIKASI'])

        if user.role in dict(Disposisi.SHARE_ROLE_CHOICES):
            filters |= Q(
                status_pengajuan='DIBAGIKAN',
                shared_recipients__role=user.role,
                shared_recipients__agreed_at__isnull=True,
            )

    if not filters:
        return Disposisi.objects.none()
    return Disposisi.objects.filter(
        filters,
        tipe_disposisi='ONLINE',
    ).distinct()


def related_disposisi_for_user(user):
    """Return every document related to the current user, including completed ones."""
    if not user.is_authenticated:
        return Disposisi.objects.none()

    if user.is_superuser or user.role == 'sekretaris':
        return Disposisi.objects.all()

    filters = Q()
    if user.role == 'direktur_utama':
        filters |= Q(
            tujuan__in=['DIRUT', 'DIREKSI'],
            status_pengajuan__in=PROCESSED_STATUSES,
        )
    elif user.role in {'direktur', 'direktur_umum'}:
        filters |= Q(
            tujuan__in=['DIR', 'DIREKSI'],
            status_pengajuan__in=PROCESSED_STATUSES,
        )

    if user.role in dict(Disposisi.SHARE_ROLE_CHOICES):
        filters |= Q(
            shared_recipients__role=user.role,
            status_pengajuan__in=SHARED_STATUSES,
        )

    if not filters:
        return Disposisi.objects.none()
    return Disposisi.objects.filter(filters).distinct()
