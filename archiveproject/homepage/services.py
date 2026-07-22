from django.db.models import Q

from disposisi.models import Disposisi


def monitor_disposisi_for_user(user):
    if not user.is_authenticated:
        return Disposisi.objects.none()

    filters = Q()
    if user.is_superuser:
        filters |= Q(status_pengajuan__in=['DIAJUKAN', 'DIISI', 'DIBAGIKAN'])
    else:
        if user.role == 'direktur_utama':
            filters |= Q(status_pengajuan='DIAJUKAN', tujuan='DIRUT')
        elif user.role in {'direktur', 'direktur_umum'}:
            filters |= Q(status_pengajuan='DIAJUKAN', tujuan='DIR')

        if user.role == 'sekretaris':
            filters |= Q(status_pengajuan='DIISI')

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
