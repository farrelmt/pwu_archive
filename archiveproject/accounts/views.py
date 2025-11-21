from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            return redirect('homepage:homepage')
        else:
            return render(request, 'login.html', {'error': 'Invalid username or password.'})

    return render(request, 'login.html')

@login_required(login_url='accounts:login')
def logout_view(request):
    auth_logout(request)
    return redirect('accounts:login')

