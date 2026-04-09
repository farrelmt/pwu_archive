from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from accounts.models import SystemUser
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

@login_required(login_url='accounts:login')
def home(request):
    return render(request, 'pengaturan.html')

@login_required(login_url='accounts:login')
def edit_profil(request, pk):
    user = request.user
    if request.user.pk != pk:
        messages.error(request, "Unauthorized access")
        return redirect('pengaturan:main')

    if request.method == 'POST':
        user.first_name = request.POST.get('first_name') or user.first_name
        user.last_name = request.POST.get('last_name') or user.last_name

        email = request.POST.get('user_email')
        if email:
            try:
                validate_email(email)
                user.email = email
            except ValidationError:
                messages.error(request, 'Invalid email format')
                return redirect('pengaturan:edit-profil', pk=pk)

        password = request.POST.get('new-password')
        repassword = request.POST.get('confirm-password')

        if password and repassword:
            if len(password) < 8 and len(password) < 8:
                messages.error(request, 'Password must be at least 8 characters.')
                return redirect('pengaturan:edit-profil', pk=pk)

            if password != repassword:
                messages.error(request, 'Passwords do not match')
                return redirect('pengaturan:edit-profil', pk=pk)
            user.set_password(password)

        user.save()
        update_session_auth_hash(request, user)

        messages.success(request, "Profil berhasil diperbarui!")
        return redirect('pengaturan:main')

    return render(request, 'edit_profil.html', {'user': user})
