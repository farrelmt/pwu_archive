from django.core.cache import cache

from .services import inbox_disposisi_for_user
from archiveproject.host_routing import portal_base_url
from archiveproject.host_routing import request_system


def notification_count_for_request(request, *, refresh=False):
    """Share the archive notification count across the view and its template."""
    if not refresh and hasattr(request, '_action_notification_count'):
        return request._action_notification_count
    cache_key = f"action-notification-count:{request.user.pk}"
    count = None if refresh else cache.get(cache_key)
    if count is None:
        count = inbox_disposisi_for_user(request.user).count()
        cache.set(cache_key, count, timeout=15)
    request._action_notification_count = count
    return count


def action_notifications(request):
    portal_url = portal_base_url(request)
    origin = request_system(request)
    base_context = {
        'portal_home_url': f'{portal_url}/',
        'portal_settings_url': f'{portal_url}/settings/?from={origin}' if origin else f'{portal_url}/settings/',
    }
    if not request.user.is_authenticated or origin != 'archive':
        return {**base_context, 'action_notification_count': 0}
    return {**base_context, 'action_notification_count': notification_count_for_request(request)}
