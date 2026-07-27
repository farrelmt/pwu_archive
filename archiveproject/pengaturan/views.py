from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from accounts.audit import record_activity

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
        changed_fields = []
        first_name = request.POST.get('first_name') or user.first_name
        last_name = request.POST.get('last_name') or user.last_name
        if first_name != user.first_name:
            user.first_name = first_name
            changed_fields.append('first_name')
        if last_name != user.last_name:
            user.last_name = last_name
            changed_fields.append('last_name')

        email = request.POST.get('user_email')
        if email:
            try:
                validate_email(email)
                if email != user.email:
                    user.email = email
                    changed_fields.append('email')
            except ValidationError:
                messages.error(request, 'Invalid email format')
                return redirect('pengaturan:edit-profil', pk=pk)

        password = request.POST.get('new-password')
        repassword = request.POST.get('confirm-password')
        current_password = request.POST.get('current-password')
        password_changed = False

        if password or repassword:
            if not current_password or not user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
                return redirect('pengaturan:edit-profil', pk=pk)

            if password != repassword:
                messages.error(request, 'Passwords do not match')
                return redirect('pengaturan:edit-profil', pk=pk)

            try:
                validate_password(password, user=user)
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
                return redirect('pengaturan:edit-profil', pk=pk)
            user.set_password(password)
            changed_fields.append('password')
            password_changed = True

        user.save()
        if password_changed:
            update_session_auth_hash(request, user)
        record_activity(
            request=request,
            category='ACCOUNT',
            action='PROFILE_UPDATED',
            description='User profile updated.',
            target_type='accounts.SystemUser',
            target_id=user.pk,
            target_label=user.username,
            metadata={'changed_fields': sorted(set(changed_fields))},
        )

        messages.success(request, "Profil berhasil diperbarui!")
        return redirect('pengaturan:main')

    return render(request, 'edit_profil.html', {'user': user})
