from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .models import AppSetting
from .forms import ReportForm
from django.conf import settings
from .services import inbox_disposisi_for_user, related_disposisi_for_user
from accounts.audit import record_activity
from accounts.models import ActivityLog
from django.core.exceptions import PermissionDenied
import textwrap
from datetime import date

@login_required(login_url='accounts:login')
def dashboard(request):
    links = []
    if request.user.can_edit_disposisi:
        links.extend([
            {"page": "disposisi", "url": "disposisi", "title": "Surat Masuk", "icon": "disposisi"},
            {"page": "nota_dinas", "url": "notadinas", "title": "Nota Dinas", "icon": "nota_dinas"},
            {"page": "surat_keluar", "url": "suratkeluar", "title": "Surat Keluar", "icon": "surat_keluar"},
        ])
    links.extend([
        {"page": "inbox", "url": "inbox", "title": "Inbox", "icon": "inbox"},
        {"page": "monitor", "url": "monitor", "title": "Monitor", "icon": "monitor"},
    ])
    if request.user.can_edit_disposisi:
        links.append({"page": "divisi", "url": "divisi", "title": "Divisi", "icon": "divisi"})
    pending_online_count = inbox_disposisi_for_user(request.user).count()
    return render(request, 'dashboard.html', {
        'links': links,
        'pending_online_count': pending_online_count,
    })

@login_required(login_url='accounts:login')
def nota_dinas(request):
    if not request.user.can_edit_disposisi:
        raise PermissionDenied
    return render(request, 'nota_dinas.html')

@login_required(login_url='accounts:login')
def surat_keluar(request):
    if not request.user.can_edit_disposisi:
        raise PermissionDenied
    return render(request, 'surat_keluar.html')


def _document_list_context(request, queryset):
    documents = queryset.order_by('-waktu_diedit')
    search = request.GET.get('search', '').strip()
    if search:
        documents = documents.filter(
            Q(nomor_agenda__icontains=search)
            | Q(nomor_surat__icontains=search)
            | Q(pengirim__icontains=search)
            | Q(perihal__icontains=search)
        )

    try:
        page_limit = int(request.GET.get('limit', 20))
    except (TypeError, ValueError):
        page_limit = 20
    if page_limit not in {20, 50, 100}:
        page_limit = 20

    paginator = Paginator(documents, page_limit)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    return {
        'page_obj': page_obj,
        'page_limit': str(page_limit),
        'search': search,
    }


@login_required(login_url='accounts:login')
def inbox(request):
    context = _document_list_context(
        request,
        inbox_disposisi_for_user(request.user),
    )
    context.update({
        'page_title': 'INBOX',
        'page_heading': 'Inbox',
        'page_description': 'Dokumen yang membutuhkan tindakan Anda.',
        'reset_url_name': 'homepage:inbox',
        'is_inbox': True,
    })
    return render(request, 'monitor.html', context)


@login_required(login_url='accounts:login')
def monitoring(request):
    context = _document_list_context(
        request,
        related_disposisi_for_user(request.user),
    )
    context.update({
        'page_title': 'MONITOR',
        'page_heading': 'Monitor Dokumen',
        'page_description': 'Semua dokumen yang berkaitan dengan Anda.',
        'reset_url_name': 'homepage:monitor',
        'is_inbox': False,
    })
    return render(request, 'monitor.html', context)

@login_required(login_url='accounts:login')
def divisi(request):
    if not request.user.can_edit_disposisi:
        raise PermissionDenied
    users = get_user_model().objects.all().order_by('role', 'username')
    return render(request, 'divisi.html', {'users': users})


@login_required(login_url='accounts:login')
def activity_log(request):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        raise PermissionDenied

    logs = ActivityLog.objects.select_related('actor').all()
    search = request.GET.get('search', '').strip()
    actor_id = request.GET.get('actor', '').strip()
    category = request.GET.get('category', '').strip()
    action = request.GET.get('action', '').strip()
    result = request.GET.get('result', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    if search:
        logs = logs.filter(
            Q(actor_username__icontains=search)
            | Q(description__icontains=search)
            | Q(target_label__icontains=search)
            | Q(ip_address__icontains=search)
        )
    if actor_id.isdigit():
        logs = logs.filter(actor_id=actor_id)
    if category in dict(ActivityLog.CATEGORY_CHOICES):
        logs = logs.filter(category=category)
    if action:
        logs = logs.filter(action=action)
    if result == 'success':
        logs = logs.filter(success=True)
    elif result == 'failed':
        logs = logs.filter(success=False)
    try:
        parsed_date_from = date.fromisoformat(date_from) if date_from else None
    except ValueError:
        parsed_date_from = None
        date_from = ''
    try:
        parsed_date_to = date.fromisoformat(date_to) if date_to else None
    except ValueError:
        parsed_date_to = None
        date_to = ''
    if parsed_date_from:
        logs = logs.filter(created_at__date__gte=parsed_date_from)
    if parsed_date_to:
        logs = logs.filter(created_at__date__lte=parsed_date_to)

    try:
        page_limit = int(request.GET.get('limit', 20))
    except (TypeError, ValueError):
        page_limit = 20
    if page_limit not in {20, 50, 100}:
        page_limit = 20

    paginator = Paginator(logs, page_limit)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(request, 'activity_log.html', {
        'page_obj': page_obj,
        'page_limit': str(page_limit),
        'search': search,
        'selected_actor': actor_id,
        'selected_category': category,
        'selected_action': action,
        'selected_result': result,
        'date_from': date_from,
        'date_to': date_to,
        'users': get_user_model().objects.order_by('username'),
        'categories': ActivityLog.CATEGORY_CHOICES,
        'actions': ActivityLog.objects.order_by('action').values_list(
            'action', flat=True
        ).distinct(),
        'query_string': query_params.urlencode(),
    })


@login_required(login_url='accounts:login')
def notifikasi(request):
    return redirect("homepage:inbox")

@login_required(login_url='accounts:login')
@never_cache
@require_http_methods(["GET", "POST"])
def report(request):
    to_email = settings.EMAIL_TO_REPORT
    form = ReportForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        title = form.cleaned_data["title"]
        description = form.cleaned_data["description"]
        steps = form.cleaned_data["steps"]
        screenshot = form.cleaned_data.get("screenshot")

        user = request.user

        email_body = textwrap.dedent(f"""
BUG REPORT 

User: {user.username}
Email: {user.email}

Title: {title}

Description: 
{description}

Steps: 
{steps}
        """).strip()

        email = EmailMessage(
            subject=f"Report Bug {title} from PWU ARCHIVE",
            body=email_body,
            to=[to_email],
        )

        if screenshot:
            email.attach(screenshot.name, screenshot.read(), screenshot.content_type)

        email.send()
        record_activity(
            request=request,
            category='SYSTEM',
            action='BUG_REPORT_SENT',
            description='Bug report sent by email.',
            target_type='homepage.Report',
            target_label=title or 'Untitled report',
        )

        messages.success(request, "Report sent successfully")
        return redirect("homepage:dashboard")

    return render(request, 'report.html', {'form': form})
