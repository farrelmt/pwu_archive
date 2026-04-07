from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from accounts.models import SystemUser
from django.shortcuts import get_object_or_404

@login_required(login_url='accounts:login')
def home(request):
    return render(request, 'pengaturan.html')

@login_required(login_url='accounts:login')
def edit_profil(request, pk):
    user = get_object_or_404(SystemUser, pk=pk)
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name') or user.first_name
        user.last_name = request.POST.get('last_name') or user.last_name
        user.email = request.POST.get('user_email') or user.email
        user.save()

        return redirect('pengaturan:main')

    return render(request, 'edit_profil.html', {'user': user})
