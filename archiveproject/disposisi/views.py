from django.shortcuts import render, get_object_or_404, redirect
from .models import Disposisi
from .forms import DisposisiForm


def list_disposisi(request):
    data = Disposisi.objects.all().order_by('-waktu_dibuat')
    return render(request, 'disposisi.html', {'data': data})

def tambah_disposisi(request):
    if request.method == "POST":
        form = DisposisiForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('disposisi:disposisi')
    else:
        form = DisposisiForm()

    return render(request, 'disposisi_tambah.html', {'form': form})


def update_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)
    form = DisposisiForm(request.POST or None, instance=disposisi)
    if form.is_valid():
        form.save()
        return redirect('disposisi:disposisi')
    return render(request, 'disposisi_edit.html', {'form': form})

def hapus_disposisi(request):
    disposisi = get_object_or_404(Disposisi, pk=request.GET.get('pk'))
    if request.method == 'POST':
        disposisi.delete()
        return redirect('disposisi:disposisi')
    return render(request, 'disposisi_hapus.html', {'disposisi': disposisi})

def filter_disposisi(request):
    return render(request, 'disposisi_tambah.html')

def detail_disposisi(request):
    if request.user.is_authenticated:
        return render(request, 'disposisi_tambah.html')
    else:
        messages.success(request, "You must be logged in to view this page.")
        return redirect('homepage')