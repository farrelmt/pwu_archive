from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.conf import settings
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from archiveproject.host_routing import request_hostname


def _login_context(request, **extra):
    is_koperasi = request_hostname(request) in settings.KOPERASI_HOSTS
    context = {
        'system_name': 'Sistem Koperasi PWU' if is_koperasi else 'Sistem Arsip PWU',
        'system_description': (
            'Kelola anggota, simpanan, pinjaman, dan keuangan koperasi '
            'seluruh grup perusahaan.'
            if is_koperasi
            else 'Kelola surat masuk, disposisi, dan pemantauan dokumen '
            'dalam satu ruang kerja yang aman.'
        ),
        'account_description': (
            'Gunakan akun Sistem Koperasi yang telah diberikan kepada Anda.'
            if is_koperasi
            else 'Gunakan akun sistem arsip yang telah diberikan kepada Anda.'
        ),
    }
    context.update(extra)
    return context

@never_cache
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            is_koperasi = request_hostname(request) in settings.KOPERASI_HOSTS
            if is_koperasi and not user.is_superuser and user.role != 'akuntan':
                return render(
                    request,
                    'login.html',
                    _login_context(
                        request,
                        error='Akun ini tidak memiliki akses ke Sistem Koperasi.',
                    ),
                )
            if not is_koperasi and not user.is_superuser and user.role == 'akuntan':
                return render(
                    request,
                    'login.html',
                    _login_context(
                        request,
                        error=(
                            'Akun Akuntan hanya dapat digunakan pada '
                            'Sistem Koperasi.'
                        ),
                    ),
                )
            auth_login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            if request_hostname(request) in settings.KOPERASI_HOSTS:
                return redirect('koperasi:dashboard')
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
    return redirect('accounts:login')
