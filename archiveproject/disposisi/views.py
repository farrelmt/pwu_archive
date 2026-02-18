from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.template.loader import render_to_string
from .models import Disposisi
from django.db.models import Q
from .forms import DisposisiForm
from datetime import datetime
from django.db.models import Max

def list_disposisi(request):
    search = request.GET.get('search', '')
    page_limit = int(request.GET.get('limit', 20))
    page_number = int(request.GET.get('page', 1))

    #Get Filter From User
    surat_day = request.GET.get('surat_day')
    surat_month = request.GET.get('surat_month')
    surat_year = request.GET.get('surat_year')
    diterima_day = request.GET.get('diterima_day')
    diterima_month = request.GET.get('diterima_month')
    diterima_year = request.GET.get('diterima_year')

    pengirim = request.GET.get('pengirim')
    tujuan = request.GET.get('tujuan')
    status = request.GET.get('status')

    #Get Disposisi Data
    sortDisposisi = request.GET.get('sort', 'tanggal_surat_diterima')
    orderDisposisi = request.GET.get('order', 'desc')

    ALLOWED_SORT = {
        'tsd': 'tanggal_surat_diterima',
        'ts': 'tanggal_surat',
    }

    sortTable = ALLOWED_SORT.get(sortDisposisi, 'tanggal_surat_diterima')

    if orderDisposisi == 'asc':
        data = Disposisi.objects.all().order_by(sortTable)
    else:
        data = Disposisi.objects.all().order_by(f'-{sortTable}')

    SEARCH_FIELDS = [
        'tanggal_surat_diterima',
        'nomor_agenda',
        'tanggal_surat',
        'nomor_surat',
        'pengirim',
        'lampiran',
        'tembusan',
        'perihal',
        'tujuan',
    ]

    TUJUAN_MAP = {
        "direktur utama": "DIRUT",
        "dirut": "DIRUT",
        "direktur": "DIR",
        "dir": "DIR",
    }

    STATUS_MAP = {
        "belum": "BELUM",
        "belum diajukan": "BELUM",
        "sudah": "SUDAH",
        "sudah diajukan": "SUDAH",
    }

    DATE_FORMATS = [
        "%Y-%m-%d",  # 2025-01-30
        "%d-%m-%Y",  # 30-01-2025
    ]

    if search:
        query = Q()
        for field in SEARCH_FIELDS:
            query |= Q(**{f"{field}__icontains": search})



        parsed_date = None
        for fmt in DATE_FORMATS:
            try:
                parsed_date = datetime.strptime(search, fmt)
                break
            except ValueError:
                continue

        # Search date with dd-mm-yy or yy-mm-dd
        if parsed_date:
            query |= Q(tanggal_surat_diterima=parsed_date)
            query |= Q(tanggal_surat=parsed_date)

        search_lower = search.lower()
        if search_lower in TUJUAN_MAP:
            query |= Q(tujuan=TUJUAN_MAP[search_lower])

        if search_lower in STATUS_MAP:
            query |= Q(status=STATUS_MAP[search_lower])

        data = data.filter(query)

    search_lower = search.lower()
    if search_lower in TUJUAN_MAP:
        data = data.filter(tujuan=TUJUAN_MAP[search_lower])

    #Use Filter
    if surat_year:
        data = data.filter(tanggal_surat__year=surat_year)

    if surat_month:
        data = data.filter(tanggal_surat__month=surat_month)

    if surat_day:
        data = data.filter(tanggal_surat__day=surat_day)

    if diterima_year:
        data = data.filter(tanggal_surat_diterima__year=diterima_year)

    if diterima_month:
        data = data.filter(tanggal_surat_diterima__month=diterima_month)

    if diterima_day:
        data = data.filter(tanggal_surat_diterima__day=diterima_day)

    if pengirim:
        data = data.filter(pengirim__icontains=pengirim)

    if tujuan:
        data = data.filter(tujuan=tujuan)

    if status:
        data = data.filter(status_pengajuan=status)

    paginator = Paginator(data, page_limit)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'page_limit': str(page_limit),
        'search': search,
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        table_html = render_to_string('partials/disposisi_table.html', context, request=request)
        pagination_html = render_to_string('partials/disposisi_pagination.html', context, request=request)

        return JsonResponse({
            'table': table_html,
            'pagination': pagination_html,
        })

    return render(request, 'disposisi.html', context)

def tambah_disposisi(request):
    next_id_agenda = (Disposisi.objects.aggregate(max_id=Max('id_agenda'))['max_id'] or 0) + 1

    if request.method == "POST":
        form = DisposisiForm(request.POST, request.FILES)
        if form.is_valid():
            disposisi = form.save(commit=False)
            disposisi.id_agenda = next_id_agenda
            disposisi.nomor_agenda = str(next_id_agenda)

            form.save()
            return redirect('disposisi:disposisi')
        else:
            print(form.errors)

    else:
        form = DisposisiForm()

    return render(request, 'disposisi_tambah.html',
                  {
                      'form': form,
                      'no_id_agenda': next_id_agenda,
                  })


def update_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)

    if request.method == "POST":
        form = DisposisiForm(request.POST, request.FILES, instance=disposisi)

        if form.is_valid():
            form.save()
            return redirect('disposisi:detaildisposisi', pk=pk)
        else:
            print(form.errors)
    else:
        form = DisposisiForm(instance=disposisi)

    return render(request, 'disposisi_edit.html', {
        'form': form,
        'disposisi': disposisi,
        'no_id_agenda': disposisi.id_agenda,
    })

def hapus_disposisi(request):
    disposisi = get_object_or_404(Disposisi, pk=request.GET.get('pk'))
    if request.method == 'POST':
        disposisi.delete()
        return redirect('disposisi'
                        ':disposisi')
    return render(request, 'disposisi_hapus.html', {'disposisi': disposisi})


def detail_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)
    if request.user.is_authenticated:
        return render(request, 'disposisi_detail.html', {
            'disposisi': disposisi
        })
    else:
        messages.success(request, "You must be logged in to view this page.")
        return redirect('homepage')