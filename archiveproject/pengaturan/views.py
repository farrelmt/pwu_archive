from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from archiveproject.host_routing import portal_base_url
from archiveproject.host_routing import request_system


def _settings_url(request):
    origin = request_system(request)
    url = f"{portal_base_url(request)}/settings/"
    return f"{url}?from={origin}" if origin else url

@login_required(login_url='accounts:login')
def home(request):
    return redirect(_settings_url(request))

@login_required(login_url='accounts:login')
def edit_profil(request, pk):
    return redirect(_settings_url(request))
