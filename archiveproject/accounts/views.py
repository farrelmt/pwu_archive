from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.http import Http404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlsplit

from archiveproject.host_routing import portal_base_url, request_hostname
from accounts.access import has_system_access


SYSTEM_HANDOFF_SALT = 'pwu-system-handoff'


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
    token = signing.dumps(
        {'user_id': request.user.pk, 'system': system},
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
    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return redirect('/')


def _can_follow_login_next(user, next_url):
    """Avoid landing a valid login directly on a known forbidden page."""
    path = urlsplit(next_url).path
    if path == '/disposisi/':
        return user.can_view_all_archive
    if path == '/disposisi/tambah/':
        return user.can_edit_disposisi
    if path.startswith('/disposisi/edit/'):
        return user.can_edit_disposisi
    return True


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
                if is_koperasi else 'Sistem Arsip PWU'
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
    if (
        request.method == 'GET'
        and request.user.is_authenticated
        and request_hostname(request) in settings.LANDING_HOSTS
    ):
        return redirect('homepage:dashboard')
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
                    return render(
                        request,
                        'login.html',
                        _login_context(
                            request,
                            error='Akun ini tidak memiliki akses ke Sistem Inventaris.',
                        ),
                    )
            if is_risk:
                from risk_management.access import has_risk_access
                if not user.is_superuser and not has_risk_access(user):
                    return render(
                        request,
                        'login.html',
                        _login_context(
                            request,
                            error='Akun ini tidak memiliki akses ke Sistem Manajemen Risiko.',
                        ),
                    )
            if is_koperasi and not user.is_superuser:
                from koperasi.access import roles_for_user
                if not roles_for_user(user):
                    return render(
                        request,
                        'login.html',
                        _login_context(
                            request,
                            error='Akun ini tidak memiliki akses ke Sistem Koperasi.',
                        ),
                    )
            auth_login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next')
            allowed_hosts = set(
                settings.LANDING_HOSTS | settings.ARCHIVE_HOSTS
                | settings.KOPERASI_HOSTS | settings.RISK_HOSTS
                | settings.INVENTORY_HOSTS
            )
            if ':' in request.get_host():
                port = request.get_host().rsplit(':', 1)[1]
                allowed_hosts |= {f'{host}:{port}' for host in tuple(allowed_hosts)}
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts=allowed_hosts,
                require_https=request.is_secure(),
            ) and _can_follow_login_next(user, next_url):
                return redirect(next_url)
            if request_hostname(request) in settings.KOPERASI_HOSTS:
                return redirect('koperasi:dashboard')
            if request_hostname(request) in settings.RISK_HOSTS:
                return redirect('risk:dashboard')
            if request_hostname(request) in settings.INVENTORY_HOSTS:
                return redirect('inventory:dashboard')
            return redirect('homepage:dashboard')
        else:
            return render(
                request,
                'login.html',
                _login_context(
                    request,
                    error='Invalid username or password.',
                ),
            )

    return render(request, 'login.html', _login_context(request))

@login_required(login_url='accounts:login')
@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect(f'{portal_base_url(request)}/accounts/login/')
