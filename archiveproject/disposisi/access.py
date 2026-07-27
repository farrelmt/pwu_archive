from django.db.models import Q

from .models import Disposisi


PROCESSED_STATUSES = {"DIAJUKAN", "DIISI", "DIBAGIKAN", "SELESAI"}
SHARED_STATUSES = {"DIBAGIKAN", "SELESAI"}


def visible_disposisi_for_user(user):
    """Return only dispositions the user is authorized to read."""
    queryset = Disposisi.objects.all()
    if not user.is_authenticated:
        return queryset.none()

    if user.is_superuser or user.can_edit_disposisi:
        return queryset

    filters = Q()
    if user.can_approve_disposisi:
        if user.role == "direktur_utama":
            filters |= Q(
                tujuan="DIRUT",
                status_pengajuan__in=PROCESSED_STATUSES,
            )
        elif user.role in {"direktur", "direktur_umum"}:
            filters |= Q(
                tujuan="DIR",
                status_pengajuan__in=PROCESSED_STATUSES,
            )

    if user.role in dict(Disposisi.SHARE_ROLE_CHOICES):
        filters |= Q(
            shared_recipients__role=user.role,
            status_pengajuan__in=SHARED_STATUSES,
        )

    if not filters:
        return queryset.none()
    return queryset.filter(filters).distinct()
