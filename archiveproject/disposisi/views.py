from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import Disposisi
from .forms import DisposisiForm

def list_disposisi(request):
    data = Disposisi.objects.all().order_by('-id')
    page_limit = int(request.GET.get('limit', 20))
    page_number = int(request.GET.get('page', 1))
    search = request.GET.get('search', '')

    if search:
        data = data.filter(perihal__icontains=search)

    paginator = Paginator(data, page_limit)
    page_obj = paginator.get_page(page_number)


    context = {
        'page_obj': page_obj,
        'page_limit': str(page_limit),
    }

    if request.headers.get('x-request-with') == 'XMLHttpRequest':
        return render(request, 'disposisi/list.html', context)


    return render(request, 'disposisi.html', context)

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
    return render(request, 'disposisi_edit.html', {
        'form': form,
        'disposisi': disposisi,
    })

def hapus_disposisi(request):
    disposisi = get_object_or_404(Disposisi, pk=request.GET.get('pk'))
    if request.method == 'POST':
        disposisi.delete()
        return redirect('disposisi'
                        ':disposisi')
    return render(request, 'disposisi_hapus.html', {'disposisi': disposisi})

def filter_disposisi(request):
    return render(request, 'disposisi_tambah.html')

def detail_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)
    if request.user.is_authenticated:
        return render(request, 'disposisi_detail.html', {
            'disposisi': disposisi
        })
    else:
        messages.success(request, "You must be logged in to view this page.")
        return redirect('homepage')