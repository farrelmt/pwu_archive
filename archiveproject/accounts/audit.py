from .models import ActivityLog


def _request_ip(request):
    if request is None:
        return None
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',', 1)[0].strip() or None
    return request.META.get('REMOTE_ADDR') or None


def record_activity(
    *,
    category,
    action,
    description='',
    request=None,
    actor=None,
    actor_username='',
    target_type='',
    target_id='',
    target_label='',
    metadata=None,
    success=True,
):
    if actor is None and request is not None:
        request_user = getattr(request, 'user', None)
        if getattr(request_user, 'is_authenticated', False):
            actor = request_user
    if not actor_username and actor is not None:
        actor_username = actor.get_username()
    user_agent = (
        request.META.get('HTTP_USER_AGENT', '')[:512]
        if request is not None
        else ''
    )
    return ActivityLog.objects.create(
        actor=actor,
        actor_username=actor_username,
        category=category,
        action=action,
        description=description,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else '',
        target_label=target_label,
        metadata=metadata or {},
        ip_address=_request_ip(request),
        user_agent=user_agent,
        success=success,
    )
