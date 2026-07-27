from .services import inbox_disposisi_for_user


def action_notifications(request):
    if not request.user.is_authenticated:
        return {'action_notification_count': 0}
    return {
        'action_notification_count': inbox_disposisi_for_user(
            request.user,
        ).count(),
    }
