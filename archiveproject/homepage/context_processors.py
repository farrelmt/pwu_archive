from django.core.cache import cache

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
    cache_key = f"action-notification-count:{request.user.pk}"
    notification_count = cache.get(cache_key)
    if notification_count is None:
        notification_count = inbox_disposisi_for_user(request.user).count()
        cache.set(cache_key, notification_count, timeout=15)
    return {**base_context, 'action_notification_count': notification_count}
