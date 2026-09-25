from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from archiveproject.host_routing import portal_base_url

@login_required(login_url='accounts:login')
def home(request):
    return redirect(f"{portal_base_url(request)}/settings/")

@login_required(login_url='accounts:login')
def edit_profil(request, pk):
    return redirect(f"{portal_base_url(request)}/settings/")
