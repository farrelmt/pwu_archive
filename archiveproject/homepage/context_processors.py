from .services import inbox_disposisi_for_user
from archiveproject.host_routing import portal_base_url


def action_notifications(request):
    portal_url = portal_base_url(request)
    base_context = {
        'portal_home_url': f'{portal_url}/',
        'portal_settings_url': f'{portal_url}/settings/',
    }
    if not request.user.is_authenticated:
        return {**base_context, 'action_notification_count': 0}
    return {**base_context,
        'action_notification_count': inbox_disposisi_for_user(
            request.user,
        ).count(),
    }
