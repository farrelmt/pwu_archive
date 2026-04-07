from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required(login_url='accounts:login')
def dashboard(request):
    links = [
        {"page": "disposisi", "url": "disposisi", "title": "Disposisi", "icon": "disposisi"},
        {"page": "nota_dinas", "url": "notadinas", "title": "Nota Dinas", "icon": "nota_dinas"},
        {"page": "surat_keluar", "url": "suratkeluar", "title": "Surat Keluar", "icon": "surat_keluar"},
        {"page": "monitor", "url": "monitor", "title": "Monitor", "icon": "monitor"},
        {"page": "divisi", "url": "divisi", "title": "Divisi", "icon": "divisi"},
    ]
    return render(request, 'dashboard.html', {'links': links})

def nota_dinas(request):
    pass

def nota_dinas(request):
    return render(request, 'nota_dinas.html')

def surat_keluar(request):
    return render(request, 'surat_keluar.html')

def monitoring(request):
    return render(request, 'monitor.html')

def divisi(request):
    return render(request, 'divisi.html')

def notifikasi(request):
    pass
