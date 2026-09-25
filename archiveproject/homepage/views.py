from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.mail import EmailMessage
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .models import AppSetting
from .forms import ReportForm
from django.conf import settings
from .services import inbox_disposisi_for_user, related_disposisi_for_user
from accounts.audit import record_activity
from accounts.models import ActivityLog
from accounts.access import can_manage_members, has_system_access, member_admin_required
from accounts.forms import MemberAccessForm, PersonalSettingsForm
from koperasi.models import KoperasiAccess
import textwrap
from datetime import date
from archiveproject.host_routing import portal_base_url, request_hostname
from django.urls import reverse


def root(request):
    hostname = request_hostname(request)
    if hostname in settings.LANDING_HOSTS:
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        archive_url = reverse('accounts:system_launch', args=['archive'])
        koperasi_url = reverse('accounts:system_launch', args=['koperasi'])
        risk_url = reverse('accounts:system_launch', args=['risk'])
        inventory_url = reverse('accounts:system_launch', args=['inventory'])

        return render(request, 'landing.html', {
            'archive_url': archive_url,
            'koperasi_url': koperasi_url,
            'risk_url': risk_url,
            'inventory_url': inventory_url,
            'can_manage_members': can_manage_members(request.user),
            'can_access_archive': has_system_access(request.user, 'archive'),
            'can_access_koperasi': has_system_access(request.user, 'koperasi'),
            'can_access_risk': has_system_access(request.user, 'risk'),
            'can_access_inventory': has_system_access(request.user, 'inventory'),
        })
    return dashboard(request)


@member_admin_required
def member_list(request):
    search = request.GET.get("search", "").strip()
    sort = request.GET.get("sort", "name")
    direction = request.GET.get("direction", "asc")
    if sort not in {"name", "username", "role", "status"}:
        sort = "name"
    if direction not in {"asc", "desc"}:
        direction = "asc"
    users = get_user_model().objects.all().order_by("first_name", "last_name", "username")
    if search:
        users = users.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
        )
    users = users.select_related("inventory_access").prefetch_related(
        "koperasi_accesses", "risk_accesses__division"
    )
    rows = []
    for user in users:
        koperasi_accesses = [
            access for access in user.koperasi_accesses.all()
            if access.company_id is None and access.is_active
        ]
        risk_accesses = [access for access in user.risk_accesses.all() if access.is_active]
        try:
            inventory_access = user.inventory_access
        except ObjectDoesNotExist:
            inventory_access = None
        roles = []
        archive_role = user.get_role_display()
        if archive_role:
            roles.append(archive_role)
        roles.extend(access.get_role_display() for access in koperasi_accesses)
        roles.extend(access.get_role_display() for access in risk_accesses)
        if inventory_access and inventory_access.is_active:
            roles.append(inventory_access.get_role_display())
        rows.append({
            "user": user,
            "roles": list(dict.fromkeys(roles)),
        })
    key_functions = {
        "name": lambda row: (row["user"].get_full_name() or "").casefold(),
        "username": lambda row: row["user"].username.casefold(),
        "role": lambda row: ", ".join(row["roles"]).casefold(),
        "status": lambda row: row["user"].is_active,
    }
    rows.sort(key=key_functions[sort], reverse=direction == "desc")
    return render(request, "member_list.html", {
        "rows": rows,
        "search": search,
        "sort": sort,
        "direction": direction,
    })


@member_admin_required
@require_http_methods(["GET", "POST"])
def member_create(request):
    form = MemberAccessForm(request.POST or None, actor=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        record_activity(
            request=request,
            category="ACCOUNT",
            action="MEMBER_CREATED",
            description=f"Membuat akun dan mengatur akses untuk {user.username}.",
            target_type="SystemUser",
            target_id=user.pk,
            target_label=user.username,
        )
        messages.success(request, f"Member {user.username} berhasil dibuat.")
        return redirect("homepage:member_list")
    return render(request, "member_form.html", {"form": form, "is_create": True})


@member_admin_required
@require_http_methods(["GET", "POST"])
def member_edit(request, pk):
    user = get_object_or_404(get_user_model(), pk=pk)
    form = MemberAccessForm(request.POST or None, instance=user, actor=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        record_activity(
            request=request,
            category="ACCOUNT",
            action="MEMBER_UPDATED",
            description=f"Memperbarui akun dan akses untuk {user.username}.",
            target_type="SystemUser",
            target_id=user.pk,
            target_label=user.username,
        )
        messages.success(request, f"Akses {user.username} berhasil diperbarui.")
        return redirect("homepage:member_list")
    return render(request, "member_form.html", {"form": form, "member": user, "is_create": False})


@member_admin_required
@require_http_methods(["GET", "POST"])
def member_delete(request, pk):
    user = get_object_or_404(get_user_model(), pk=pk)
    if user == request.user:
        messages.error(request, "Anda tidak dapat menghapus akun yang sedang digunakan.")
        return redirect("homepage:member_edit", pk=user.pk)

    has_disposition_history = user.userlog.exists()
    if request.method == "POST":
        if has_disposition_history:
            messages.error(
                request,
                "Akun memiliki riwayat disposisi dan tidak dapat dihapus. "
                "Nonaktifkan akun untuk mempertahankan histori.",
            )
            return redirect("homepage:member_edit", pk=user.pk)

        username = user.username
        user_pk = user.pk
        try:
            user.delete()
        except ProtectedError:
            messages.error(
                request,
                "Akun masih digunakan oleh data operasional dan tidak dapat dihapus. "
                "Nonaktifkan akun sebagai gantinya.",
            )
            return redirect("homepage:member_edit", pk=user_pk)

        record_activity(
            request=request,
            category="ACCOUNT",
            action="MEMBER_DELETED",
            description=f"Menghapus akun {username}.",
            target_type="SystemUser",
            target_id=user_pk,
            target_label=username,
        )
        messages.success(request, f"Akun {username} berhasil dihapus.")
        return redirect("homepage:member_list")

    return render(request, "member_confirm_delete.html", {
        "member": user,
        "has_disposition_history": has_disposition_history,
    })


@login_required(login_url="accounts:login")
@require_http_methods(["GET", "POST"])
def personal_settings(request):
    if request_hostname(request) not in settings.LANDING_HOSTS:
        return redirect(f"{portal_base_url(request)}/settings/")
    user = request.user
    original = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
    }
    form = PersonalSettingsForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        password_changed = bool(form.cleaned_data.get("new_password"))
        user = form.save()
        if password_changed:
            update_session_auth_hash(request, user)
        changed_fields = [
            field_name
            for field_name, old_value in original.items()
            if getattr(user, field_name) != old_value
        ]
        if password_changed:
            changed_fields.append("password")
        record_activity(
            request=request,
            category="ACCOUNT",
            action="PROFILE_UPDATED",
            description="Pengguna memperbarui profil pribadinya.",
            target_type="SystemUser",
            target_id=user.pk,
            target_label=user.username,
            metadata={"changed_fields": changed_fields},
        )
        messages.success(request, "Informasi akun berhasil diperbarui.")
        return redirect("homepage:personal_settings")
    return render(request, "personal_settings.html", {"form": form})


@login_required(login_url='accounts:login')
def dashboard(request):
    links = []
    if request.user.can_view_all_archive:
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
    if not request.user.can_view_all_archive:
        raise PermissionDenied
    return render(request, 'nota_dinas.html')

@login_required(login_url='accounts:login')
def surat_keluar(request):
    if not request.user.can_view_all_archive:
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
    users = get_user_model().objects.prefetch_related(
        'koperasi_accesses__company',
        'risk_accesses__division',
    ).select_related(
        'inventory_access',
    ).order_by('role', 'username')
    directory_rows = []
    for system_user in users:
        koperasi_access = [
            (
                row.get_role_display()
                + (f" · {row.company.name}" if row.company else " · Semua perusahaan")
            )
            for row in system_user.koperasi_accesses.all()
            if row.is_active
        ]
        risk_accesses = [row for row in system_user.risk_accesses.all() if row.is_active]
        inventory_access = getattr(system_user, 'inventory_access', None)
        directory_rows.append({
            'user': system_user,
            'archive_access': system_user.get_role_display() or 'Pengguna',
            'koperasi_access': koperasi_access,
            'risk_access': ', '.join(
                row.get_role_display()
                + (f" · {row.division.name}" if row.division else " · Semua divisi")
                for row in risk_accesses
            ) or '-',
            'inventory_access': (
                inventory_access.get_role_display()
                if inventory_access and inventory_access.is_active else '-'
            ),
        })
    return render(request, 'divisi.html', {
        'directory_rows': directory_rows,
        'directory_total': len(directory_rows),
    })


@login_required(login_url='accounts:login')
def activity_log(request):
    if not request.user.can_view_activity_log:
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
