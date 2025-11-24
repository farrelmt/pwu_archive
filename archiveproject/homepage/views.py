from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required(login_url='accounts:login')
def home(request):
    return render(request, 'home.html')

def disposisi(request):
    return render(request, 'disposisi.html')

def nota_dinas(request):
    return render(request, 'notadinas.html')

def surat_keluar(request):
    return render(request, 'suratkeluar.html')

def monitoring(request):
    return render(request, 'monitoring.html')

def divisi(request):
    return render(request, 'divisi.html')

def pengaturan(request):
    return render(request, 'pengaturan.html')

def notifikasi(request):
    pass