from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required(login_url='accounts:login')
def dashboard(request):
    links = [
        {"page": "beranda", "url": "", "title": "Beranda"},
        {"page": "disposisi", "url": "disposisi.html", "title": "Disposisi"},
        {"page": "nota_dinas", "url": "nota_dinas.html", "title": "Nota Dinas"},
        {"page": "surat_keluar", "url": "surat_keluar.html", "title": "Surat Keluar"},
        {"page": "monitor", "url": "monitoring.html", "title": "Monitor"},
        {"page": "divisi", "url": "divisi.html", "title": "Divisi"},
    ]
    return render(request, 'dashboard.html', {'links': links})

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
