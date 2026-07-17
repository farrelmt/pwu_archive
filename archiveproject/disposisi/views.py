from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.template.loader import render_to_string
from django.db.models import Q, Max
from .models import Disposisi
from .models import DisposisiLog
from .forms import DisposisiForm
from datetime import datetime
from collections import defaultdict
from django.utils.timezone import localtime
from django.contrib import messages
from weasyprint import HTML
from django.contrib.auth.decorators import login_required
import os

@login_required
def list_disposisi(request):
    search = request.GET.get('search', '')
    try:
        page_limit = int(request.GET.get('limit', 20))
    except ValueError:
        page_limit = 20

    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1

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
        'na': 'nomor_agenda',
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

    # search_lower = search.lower()
    # if search_lower in TUJUAN_MAP:
    #     data = data.filter(tujuan=TUJUAN_MAP[search_lower])

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

def create_log(disposisi, user, action, desc=""):
    DisposisiLog.objects.create(
        disposisi= disposisi,
        user_log= user,
        action_log= action,
        keterangan_log  = desc
    )

@login_required
def tambah_disposisi(request):
    if request.method == "POST":
        form = DisposisiForm(request.POST, request.FILES)
        if form.is_valid():
            disposisi = form.save()

            create_log(disposisi, request.user, 'DIBUAT')
            return redirect('disposisi:disposisi')
        else:
            print(form.errors)

    else:
        form = DisposisiForm()

    next_id_agenda =  Disposisi.objects.values('tanggal_surat_diterima').distinct().count() + 1

    return render(request, 'disposisi_tambah.html',{
        'form': form,
        'no_id_agenda': next_id_agenda,
    })

@login_required
def update_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)

    if request.method == "POST":
        form = DisposisiForm(request.POST, request.FILES, instance=disposisi)
        if form.is_valid():
            disposisi = form.save(commit=False)
            if disposisi.status_pengajuan == "DIISI":
                disposisi.status_pengajuan = "DIAJUKAN"
                if disposisi.dokumen_disposisi and os.path.isfile(disposisi.dokumen_disposisi.path):
                    os.remove(disposisi.dokumen_disposisi.path)
                disposisi.dokumen_disposisi = "EMPTY"

            disposisi.status_pengajuan = 'DIBUAT'
            disposisi.save()

            create_log(disposisi, request.user, 'DIEDIT')
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

@login_required
def hapus_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)
    if disposisi.dokumen_surat_masuk and os.path.isfile(disposisi.dokumen_surat_masuk.path):
        try:
            os.remove(disposisi.dokumen_surat_masuk.path)
        except Exception as e:
            messages.error(request, f'File tidak bisa dihapus : {e}')
    if disposisi.dokumen_disposisi and os.path.isfile(disposisi.dokumen_disposisi.path):
        try:
            os.remove(disposisi.dokumen_disposisi.path)
        except Exception as e:
            messages.error(request, f'File tidak bisa dihapus : {e}')
    create_log(disposisi, request.user, 'DIHAPUS')
    disposisi.delete()
    return redirect('disposisi:disposisi')

@login_required
def detail_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)

    logs = disposisi.logs.select_related('user_log').all()

    grouped_logs = defaultdict(list)

    HARI_ID = {
        'Monday': 'Senin',
        'Tuesday': 'Selasa',
        'Wednesday': 'Rabu',
        'Thursday': 'Kamis',
        'Friday': 'Jumat',
        'Saturday': 'Sabtu',
        'Sunday': 'Minggu',
    }

    for log in logs:
        local_time = localtime(log.waktu)
        hari_en = local_time.strftime('%A')
        hari_id = HARI_ID.get(hari_en, hari_en)
        date_key = f"{hari_id}, {local_time.strftime('%d/%m/%Y')}"

        grouped_logs[date_key].append({
            'time': local_time.strftime('%H:%M'),
            'user': log.user_log.username,
            'action': log.get_action_log_display(),
            'desc': log.keterangan_log
        })


    if request.user.is_authenticated:
        return render(request, 'disposisi_detail.html', {
            'disposisi': disposisi,
            'grouped_logs': dict(grouped_logs),
        })
    else:
        messages.success(request, "You must be logged in to view this page.")
        return redirect('accounts:login')

@login_required
def preview_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)
    return render(request, 'disposisi_preview.html', {'disposisi': disposisi})

@login_required
def upload_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)

    if request.method == "POST":
        file = request.FILES.get('dokumen_disposisi')

        if file:
            disposisi.dokumen_disposisi = file
            disposisi.status_pengajuan = 'SELESAI'
            disposisi.save()

            create_log(disposisi, request.user, 'UPLOAD_DISPOSISI')

            return redirect('disposisi:detaildisposisi', pk=pk)
        else:
            messages.error(request, "File not found.")

    return render(request, 'disposisi_upload.html', {
        'disposisi': disposisi
    })

@login_required
def edit_file_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)

    if request.method == "POST":
        file = request.FILES.get('dokumen_disposisi')

        if file:
            if disposisi.dokumen_disposisi and os.path.isfile(disposisi.dokumen_disposisi.path):
                try:
                    os.remove(disposisi.dokumen_disposisi.path)
                except Exception as e:
                    messages.error(request, e)

            disposisi.dokumen_disposisi = file
            disposisi.save()

            create_log(disposisi, request.user, 'DIEDIT')

            return redirect('disposisi:detaildisposisi', pk=pk)
        else:
            messages.error(request, "Tidak ada file yang dipilih.")

        return render(request, 'disposisi_edit_file.html', {'disposisi': disposisi})

@login_required
def download_disposisi_pdf(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)

    html_string = render_to_string(
        'disposisi_pdf.html',
        {'disposisi': disposisi}
    )

    response = HttpResponse(content_type='application/pdf')
    filename = f'Disposisi-{disposisi.nomor_agenda}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/')
    ).write_pdf(response)

    return response