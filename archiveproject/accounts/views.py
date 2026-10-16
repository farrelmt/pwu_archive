from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlencode, urlsplit

from archiveproject.host_routing import portal_base_url, request_hostname
from accounts.access import has_system_access


SYSTEM_HANDOFF_SALT = 'pwu-system-handoff'


def _is_async_login(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _login_error(request, message, next_url, *, status=401):
    if _is_async_login(request):
        return JsonResponse({'ok': False, 'error': message}, status=status)
    return render(
        request,
        'login.html',
        _login_context(request, error=message, next_url=next_url),
    )


def _login_success(request, destination):
    if _is_async_login(request):
        return JsonResponse({'ok': True, 'redirect_url': destination})
    return redirect(destination)


def _system_hosts_and_url(request, system):
    systems = {
        'archive': (settings.ARCHIVE_HOSTS, settings.ARCHIVE_BASE_URL),
        'koperasi': (settings.KOPERASI_HOSTS, settings.KOPERASI_BASE_URL),
        'risk': (settings.RISK_HOSTS, settings.RISK_BASE_URL),
        'inventory': (settings.INVENTORY_HOSTS, settings.INVENTORY_BASE_URL),
    }
    if system not in systems:
        raise Http404
    hosts, production_url = systems[system]
    hostname = request_hostname(request)
    if hostname == 'localhost' or hostname.endswith('.localhost'):
        requested_host = request.get_host()
        port_suffix = f":{requested_host.rsplit(':', 1)[1]}" if ':' in requested_host else ''
        return hosts, f'http://{system}.localhost{port_suffix}'
    return hosts, production_url.rstrip('/')


@login_required(login_url='accounts:login')
def system_launch(request, system):
    """Move a portal login safely onto a system subdomain.

    Browsers do not reliably share cookies from ``localhost`` with
    ``*.localhost``. A short-lived signed handoff creates a normal session on
    the selected host without exposing credentials or a reusable login URL.
    """
    if request_hostname(request) not in settings.LANDING_HOSTS:
        raise Http404
    _hosts, base_url = _system_hosts_and_url(request, system)
    if not has_system_access(request.user, system):
        raise PermissionDenied("Akun Anda tidak memiliki akses ke sistem ini.")
    next_path = request.GET.get('next', '/')
    if (
        not next_path.startswith('/')
        or next_path.startswith('//')
        or not _can_follow_login_next(request.user, next_path)
    ):
        next_path = '/'
    token = signing.dumps(
        {
            'user_id': request.user.pk,
            'system': system,
            'next_path': next_path,
        },
        salt=SYSTEM_HANDOFF_SALT,
        compress=True,
    )
    return redirect(f'{base_url}/accounts/handoff/?token={token}')


@never_cache
def system_handoff(request):
    token = request.GET.get('token', '')
    try:
        payload = signing.loads(token, salt=SYSTEM_HANDOFF_SALT, max_age=60)
        system = payload['system']
        user_id = payload['user_id']
        next_path = payload.get('next_path', '/')
    except (signing.BadSignature, KeyError, TypeError):
        return redirect(f'{portal_base_url(request)}/accounts/login/')

    expected_hosts, _base_url = _system_hosts_and_url(request, system)
    if request_hostname(request) not in expected_hosts:
        raise Http404
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        return redirect(f'{portal_base_url(request)}/accounts/login/')
    if not has_system_access(user, system):
        raise PermissionDenied("Akun Anda tidak memiliki akses ke sistem ini.")
    if (
        not isinstance(next_path, str)
        or not next_path.startswith('/')
        or next_path.startswith('//')
        or not _can_follow_login_next(user, next_path)
    ):
        next_path = '/'
    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return redirect(next_path)


def _can_follow_login_next(user, next_url):
    """Avoid landing a valid login directly on a known forbidden page."""
    parsed_url = urlsplit(next_url)
    if parsed_url.hostname in settings.KOPERASI_HOSTS:
        return has_system_access(user, "koperasi")
    path = parsed_url.path
    if path == '/disposisi/':
        return user.can_view_all_archive
    if path == '/disposisi/tambah/':
        return user.can_edit_disposisi
    if path.startswith('/disposisi/edit/'):
        return user.can_edit_disposisi
    return True


def _allowed_login_hosts(request):
    allowed_hosts = set(
        settings.LANDING_HOSTS | settings.ARCHIVE_HOSTS
        | settings.KOPERASI_HOSTS | settings.RISK_HOSTS
        | settings.INVENTORY_HOSTS
    )
    if ':' in request.get_host():
        port = request.get_host().rsplit(':', 1)[1]
        allowed_hosts |= {f'{host}:{port}' for host in tuple(allowed_hosts)}
    return allowed_hosts


def _login_destination(request, user, next_url):
    """Validate login targets and route Archive via a reliable GET handoff."""
    if not next_url or not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts=_allowed_login_hosts(request),
        require_https=request.is_secure(),
    ) or not _can_follow_login_next(user, next_url):
        return None

    parsed_url = urlsplit(next_url)
    if (
        parsed_url.hostname in settings.ARCHIVE_HOSTS
        and request_hostname(request) in settings.LANDING_HOSTS
    ):
        archive_path = parsed_url.path or '/'
        if parsed_url.query:
            archive_path = f'{archive_path}?{parsed_url.query}'
        launch_url = reverse('accounts:system_launch', args=['archive'])
        return f'{launch_url}?{urlencode({"next": archive_path})}'
    return next_url


def _successful_login_destination(request, user, next_url):
    destination = _login_destination(request, user, next_url)
    if destination:
        return destination
    if request_hostname(request) in settings.KOPERASI_HOSTS:
        return reverse('koperasi:dashboard')
    if request_hostname(request) in settings.RISK_HOSTS:
        return reverse('risk:dashboard')
    if request_hostname(request) in settings.INVENTORY_HOSTS:
        return reverse('inventory:dashboard')
    return reverse('homepage:dashboard')


@never_cache
def login_status(request):
    """Let a stalled login page recover only after its session is established."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'authenticated': False})
    return JsonResponse({
        'authenticated': True,
        'destination': _successful_login_destination(
            request, request.user, request.GET.get('next', ''),
        ),
    })


def _login_context(request, **extra):
    is_portal = request_hostname(request) in settings.LANDING_HOSTS
    is_koperasi = request_hostname(request) in settings.KOPERASI_HOSTS
    is_risk = request_hostname(request) in settings.RISK_HOSTS
    is_inventory = request_hostname(request) in settings.INVENTORY_HOSTS
    context = {
        'is_koperasi': is_koperasi,
        'is_risk': is_risk,
        'is_inventory': is_inventory,
        'is_portal': is_portal,
        'system_name': (
            'Portal Sistem Informasi PWU Jatim'
            if is_portal else (
            'Sistem Inventaris PWU'
            if is_inventory else (
                'Sistem Manajemen Risiko'
                if is_risk else (
                'Koperasi Karyawan Wira Jatim'
                if is_koperasi else 'Sistem PWU'
                )
            ))
        ),
        'system_description': (
            ''
            if is_portal else (
            'Kelola data pegawai, perangkat keras, dan aset perusahaan '
            'dalam satu inventaris terpusat.'
            if is_inventory else (
                'Identifikasi, nilai, mitigasi, dan pantau risiko perusahaan '
                'secara terintegrasi.'
                if is_risk else (
                'Kelola anggota, simpan pinjam, Sie Usaha, kas dan bank, '
                'laporan keuangan, serta pembagian SHU.'
                if is_koperasi else
                'Kelola surat masuk, disposisi, dan pemantauan dokumen '
                'dalam satu ruang kerja yang aman.'
                )
            ))
        ),
        'account_description': (
            'Gunakan akun PWU Jatim yang telah diberikan kepada Anda.'
            if is_portal else (
            'Gunakan akun Sistem Inventaris yang telah diberikan kepada Anda.'
            if is_inventory else (
                'Gunakan akun Manajemen Risiko yang telah diberikan kepada Anda.'
                if is_risk else (
                'Gunakan akun Sistem Koperasi yang telah diberikan kepada Anda.'
                if is_koperasi else
                'Gunakan akun sistem arsip yang telah diberikan kepada Anda.'
                )
            ))
        ),
    }
    context.update(extra)
    return context

@never_cache
def login_view(request):
    next_url = request.POST.get('next') or request.GET.get('next', '')
    if (
        request.method == 'GET'
        and request.user.is_authenticated
        and request_hostname(request) in settings.LANDING_HOSTS
    ):
        return redirect(_successful_login_destination(request, request.user, next_url))
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            is_koperasi = request_hostname(request) in settings.KOPERASI_HOSTS
            is_risk = request_hostname(request) in settings.RISK_HOSTS
            is_inventory = request_hostname(request) in settings.INVENTORY_HOSTS
            if is_inventory:
                from inventory.access import has_inventory_access
                if not user.is_superuser and not has_inventory_access(user):
                    return _login_error(
                        request,
                        'Akun ini tidak memiliki akses ke Sistem Inventaris.',
                        next_url,
                        status=403,
                    )
            if is_risk:
                from risk_management.access import has_risk_access
                if not user.is_superuser and not has_risk_access(user):
                    return _login_error(
                        request,
                        'Akun ini tidak memiliki akses ke Sistem Manajemen Risiko.',
                        next_url,
                        status=403,
                    )
            if is_koperasi:
                if not has_system_access(user, "koperasi"):
                    return _login_error(
                        request,
                        'Akun ini tidak memiliki akses ke Sistem Koperasi.',
                        next_url,
                        status=403,
                    )
            auth_login(request, user)
            return _login_success(
                request,
                _successful_login_destination(request, user, next_url),
            )
        else:
            return _login_error(
                request,
                'Invalid username or password.',
                next_url,
            )

    return render(
        request,
        'login.html',
        _login_context(request, next_url=next_url),
    )

@login_required(login_url='accounts:login')
@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect(f'{portal_base_url(request)}/accounts/login/')
