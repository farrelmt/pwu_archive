from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from .models import ActivityLog


@login_required(login_url="accounts:login")
def system_activity_log(
    request,
    *,
    category,
    system_name,
    base_template,
    activity_url_name,
):
    """Render a read-only, system-scoped audit trail for superusers."""
    if not request.user.is_superuser:
        raise PermissionDenied("Hanya superuser yang dapat melihat log aktivitas.")

    logs = ActivityLog.objects.select_related("actor").filter(category=category)
    search = request.GET.get("search", "").strip()
    actor_id = request.GET.get("actor", "").strip()
    action = request.GET.get("action", "").strip()
    result = request.GET.get("result", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if search:
        logs = logs.filter(
            Q(actor_username__icontains=search)
            | Q(action__icontains=search)
            | Q(description__icontains=search)
            | Q(target_label__icontains=search)
            | Q(ip_address__icontains=search)
        )
    if actor_id.isdigit():
        logs = logs.filter(actor_id=actor_id)
    if action:
        logs = logs.filter(action=action)
    if result == "success":
        logs = logs.filter(success=True)
    elif result == "failed":
        logs = logs.filter(success=False)

    try:
        parsed_date_from = date.fromisoformat(date_from) if date_from else None
    except ValueError:
        parsed_date_from = None
        date_from = ""
    try:
        parsed_date_to = date.fromisoformat(date_to) if date_to else None
    except ValueError:
        parsed_date_to = None
        date_to = ""
    if parsed_date_from:
        logs = logs.filter(created_at__date__gte=parsed_date_from)
    if parsed_date_to:
        logs = logs.filter(created_at__date__lte=parsed_date_to)

    try:
        page_limit = int(request.GET.get("limit", 20))
    except (TypeError, ValueError):
        page_limit = 20
    if page_limit not in {20, 50, 100}:
        page_limit = 20

    page_obj = Paginator(logs, page_limit).get_page(request.GET.get("page", 1))
    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(request, "accounts/system_activity_log.html", {
        "base_template": base_template,
        "system_name": system_name,
        "activity_url_name": activity_url_name,
        "page_obj": page_obj,
        "page_limit": str(page_limit),
        "search": search,
        "selected_actor": actor_id,
        "selected_action": action,
        "selected_result": result,
        "date_from": date_from,
        "date_to": date_to,
        "users": get_user_model().objects.filter(
            activity_logs__category=category,
        ).distinct().order_by("username"),
        "actions": ActivityLog.objects.filter(category=category).order_by(
            "action",
        ).values_list("action", flat=True).distinct(),
        "query_string": query_params.urlencode(),
    })
