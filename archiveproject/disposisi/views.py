from django.shortcuts import render, get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.template.loader import render_to_string
from django.db import transaction
from django.db.models import Q, Max
from .models import Disposisi, DisposisiLog, DisposisiRecipient
from .forms import (
    DisposisiForm,
    DisposisiUploadForm,
    OnlineDisposisiIsiForm,
    ShareDisposisiForm,
)
from .decorators import disposisi_director_required, disposisi_editor_required
from datetime import datetime
from collections import defaultdict
from django.utils import timezone
from django.utils.timezone import localtime
from django.contrib import messages
from weasyprint import HTML
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

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
@disposisi_editor_required
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
@disposisi_editor_required
def update_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)

    if request.method == "POST":
        form = DisposisiForm(request.POST, request.FILES, instance=disposisi)
        if form.is_valid():
            disposisi = form.save(commit=False)
            if disposisi.status_pengajuan == "DIISI" and disposisi.dokumen_disposisi:
                disposisi.dokumen_disposisi = None
            disposisi.isi_disposisi = ''
            disposisi.status_pengajuan = 'DIBUAT'
            disposisi.save()
            disposisi.shared_recipients.all().delete()

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
@disposisi_editor_required
@require_POST
def hapus_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)
    files = [disposisi.dokumen_surat_masuk, disposisi.dokumen_disposisi]
    disposisi.delete()
    for document in files:
        if document:
            document.storage.delete(document.name)
    return redirect('disposisi:disposisi')

@login_required
def detail_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)
    share_recipient = disposisi.shared_recipients.filter(
        role=request.user.role,
    ).first()

    logs = disposisi.logs.select_related('user_log').all()
    can_share_this_disposisi = (
        disposisi.status_pengajuan == 'DIISI'
        and (
            (
                disposisi.tipe_disposisi == 'ONLINE'
                and request.user.can_share_disposisi
            )
            or (
                disposisi.tipe_disposisi == 'OFFLINE'
                and request.user.can_edit_disposisi
            )
        )
    )

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
            'share_role_choices': Disposisi.SHARE_ROLE_CHOICES,
            'can_approve_this_disposisi': disposisi.can_be_approved_by(
                request.user,
            ),
            'is_share_recipient': share_recipient is not None,
            'share_recipient': share_recipient,
            'can_share_this_disposisi': can_share_this_disposisi,
            'selected_recipient_roles': list(
                disposisi.shared_recipients.values_list('role', flat=True)
            ),
        })
    else:
        messages.success(request, "You must be logged in to view this page.")
        return redirect('accounts:login')

@login_required
def preview_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)
    return render(request, 'disposisi_preview.html', {
        'disposisi': disposisi,
        'selected_recipient_roles': list(
            disposisi.shared_recipients.values_list('role', flat=True)
        ),
    })

@login_required
@disposisi_editor_required
def upload_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)
    share_form = ShareDisposisiForm(request.POST or None)

    if request.method == "POST":
        if disposisi.status_pengajuan != 'DIBUAT':
            messages.error(request, "Disposisi ini sudah diproses.")
            return redirect('disposisi:detaildisposisi', pk=pk)

        metode = request.POST.get('metode')
        if not share_form.is_valid():
            messages.error(request, share_form.errors['recipients'][0])
            form = DisposisiUploadForm(
                request.POST,
                request.FILES,
                instance=disposisi,
            )
            return render(request, 'disposisi_upload.html', {
                'disposisi': disposisi,
                'form': form,
                'share_form': share_form,
            })

        selected_roles = share_form.cleaned_data['recipients']
        role_labels = dict(Disposisi.SHARE_ROLE_CHOICES)
        recipient_names = ', '.join(role_labels[role] for role in selected_roles)

        if metode == 'ONLINE':
            with transaction.atomic():
                disposisi = Disposisi.objects.select_for_update().get(pk=pk)
                if disposisi.status_pengajuan != 'DIBUAT':
                    messages.error(request, "Disposisi ini sudah diproses.")
                    return redirect('disposisi:detaildisposisi', pk=pk)
                disposisi.dokumen_disposisi = None
                disposisi.isi_disposisi = ''
                disposisi.tipe_disposisi = 'ONLINE'
                disposisi.status_pengajuan = 'DIAJUKAN'
                disposisi.save(update_fields=[
                    'dokumen_disposisi', 'isi_disposisi', 'tipe_disposisi',
                    'status_pengajuan', 'waktu_diedit'
                ])
                disposisi.shared_recipients.all().delete()
                DisposisiRecipient.objects.bulk_create([
                    DisposisiRecipient(disposisi=disposisi, role=role)
                    for role in selected_roles
                ])
                create_log(
                    disposisi,
                    request.user,
                    'AJUKAN_DISPOSISI',
                    f'Pengajuan disposisi online dikirim ke Direktur dan akan '
                    f'dibagikan kepada: {recipient_names}.',
                )
            messages.success(request, "Pengajuan online dikirim ke Direktur.")
            return redirect('disposisi:detaildisposisi', pk=pk)

        if metode != 'OFFLINE':
            messages.error(request, "Pilih metode disposisi yang valid.")
            return redirect('disposisi:uploaddisposisi', pk=pk)

        form = DisposisiUploadForm(request.POST, request.FILES, instance=disposisi)
        if form.is_valid():
            with transaction.atomic():
                disposisi = form.save(commit=False)
                disposisi.tipe_disposisi = 'OFFLINE'
                disposisi.status_pengajuan = 'SELESAI'
                disposisi.save()
                disposisi.shared_recipients.all().delete()
                DisposisiRecipient.objects.bulk_create([
                    DisposisiRecipient(disposisi=disposisi, role=role)
                    for role in selected_roles
                ])
                create_log(
                    disposisi,
                    request.user,
                    'UPLOAD_DISPOSISI',
                    'File disposisi offline berhasil diunggah.',
                )
                create_log(
                    disposisi,
                    request.user,
                    'BAGI_DISPOSISI',
                    f'Disposisi dibagikan kepada: {recipient_names}.',
                )
                create_log(
                    disposisi,
                    request.user,
                    'SELESAI',
                    'Disposisi offline selesai setelah file diunggah dan '
                    'penerima dipilih.',
                )

            return redirect('disposisi:detaildisposisi', pk=pk)
    else:
        form = DisposisiUploadForm(instance=disposisi)

    return render(request, 'disposisi_upload.html', {
        'disposisi': disposisi,
        'form': form,
        'share_form': share_form,
    })


@login_required
@disposisi_editor_required
@require_POST
def cancel_online_disposisi(request, pk):
    with transaction.atomic():
        disposisi = get_object_or_404(
            Disposisi.objects.select_for_update(), pk=pk
        )
        if not (
            disposisi.tipe_disposisi == 'ONLINE'
            and disposisi.status_pengajuan == 'DIAJUKAN'
        ):
            messages.error(request, "Pengajuan online ini tidak dapat dibatalkan.")
            return redirect('disposisi:detaildisposisi', pk=pk)

        disposisi.tipe_disposisi = 'BELUM'
        disposisi.status_pengajuan = 'DIBUAT'
        disposisi.isi_disposisi = ''
        disposisi.save(update_fields=[
            'tipe_disposisi', 'status_pengajuan', 'isi_disposisi',
            'waktu_diedit'
        ])
        disposisi.shared_recipients.all().delete()
        create_log(
            disposisi,
            request.user,
            'BATAL_PENGAJUAN',
            'Pengajuan disposisi online dibatalkan.',
        )

    messages.success(request, "Pengajuan online dibatalkan.")
    return redirect('disposisi:detaildisposisi', pk=pk)


@login_required
@disposisi_director_required
@require_POST
def decide_online_disposisi(request, pk):
    requested_disposisi = get_object_or_404(Disposisi, pk=pk)
    if not requested_disposisi.can_be_approved_by(request.user):
        raise PermissionDenied

    keputusan = request.POST.get('keputusan')
    if keputusan == 'SETUJUI':
        return redirect('disposisi:isionline', pk=pk)
    if keputusan != 'TOLAK':
        messages.error(request, "Keputusan tidak valid.")
        return redirect('homepage:monitor')

    with transaction.atomic():
        disposisi = get_object_or_404(
            Disposisi.objects.select_for_update(), pk=pk
        )
        if not disposisi.can_be_approved_by(request.user):
            raise PermissionDenied
        if not (
            disposisi.tipe_disposisi == 'ONLINE'
            and disposisi.status_pengajuan == 'DIAJUKAN'
        ):
            messages.error(request, "Pengajuan ini sudah diproses.")
            return redirect('homepage:monitor')

        alasan = request.POST.get('alasan', '').strip()
        disposisi.tipe_disposisi = 'BELUM'
        disposisi.status_pengajuan = 'DIBUAT'
        disposisi.isi_disposisi = ''
        action = 'TOLAK_DISPOSISI'
        description = alasan or 'Pengajuan online ditolak oleh Direktur.'
        success_message = "Pengajuan online ditolak."

        disposisi.save(update_fields=[
            'tipe_disposisi', 'status_pengajuan', 'isi_disposisi',
            'waktu_diedit'
        ])
        disposisi.shared_recipients.all().delete()
        create_log(disposisi, request.user, action, description)

    messages.success(request, success_message)
    return redirect('homepage:monitor')


@login_required
def isi_online_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)
    is_pending = (
        disposisi.tipe_disposisi == 'ONLINE'
        and disposisi.status_pengajuan == 'DIAJUKAN'
    )
    is_approved = (
        disposisi.tipe_disposisi == 'ONLINE'
        and disposisi.status_pengajuan in {'DIISI', 'DIBAGIKAN', 'SELESAI'}
    )

    if not (is_pending or is_approved):
        messages.error(request, "Disposisi online ini tidak tersedia untuk diisi.")
        return redirect('disposisi:detaildisposisi', pk=pk)

    can_approve_this = disposisi.can_be_approved_by(request.user)
    if is_pending and not can_approve_this:
        raise PermissionDenied

    read_only = is_approved
    if request.method == 'POST':
        if read_only or not can_approve_this:
            raise PermissionDenied

        form = OnlineDisposisiIsiForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                locked_disposisi = get_object_or_404(
                    Disposisi.objects.select_for_update(), pk=pk
                )
                if not (
                    locked_disposisi.tipe_disposisi == 'ONLINE'
                    and locked_disposisi.status_pengajuan == 'DIAJUKAN'
                ):
                    messages.error(request, "Pengajuan ini sudah diproses.")
                    return redirect('homepage:monitor')
                if not locked_disposisi.can_be_approved_by(request.user):
                    raise PermissionDenied

                locked_disposisi.isi_disposisi = form.cleaned_data['isi_disposisi']
                has_recipients = locked_disposisi.shared_recipients.exists()
                locked_disposisi.status_pengajuan = (
                    'DIBAGIKAN' if has_recipients else 'DIISI'
                )
                locked_disposisi.save(update_fields=[
                    'isi_disposisi', 'status_pengajuan', 'waktu_diedit'
                ])
                create_log(
                    locked_disposisi,
                    request.user,
                    'SETUJUI_DISPOSISI',
                    'Isi disposisi online dikirim dan disetujui oleh Direktur.',
                )
                if has_recipients:
                    role_labels = dict(Disposisi.SHARE_ROLE_CHOICES)
                    selected_roles = list(
                        locked_disposisi.shared_recipients.values_list(
                            'role', flat=True
                        )
                    )
                    recipient_names = ', '.join(
                        role_labels[role] for role in selected_roles
                    )
                    create_log(
                        locked_disposisi,
                        request.user,
                        'BAGI_DISPOSISI',
                        f'Disposisi dibagikan kepada: {recipient_names}.',
                    )

            messages.success(request, "Isi disposisi berhasil dikirim dan disetujui.")
            return redirect('disposisi:detaildisposisi', pk=pk)
    else:
        form = OnlineDisposisiIsiForm(instance=disposisi)

    return render(request, 'disposisi_isi_online.html', {
        'disposisi': disposisi,
        'form': form,
        'read_only': read_only,
        'selected_recipient_roles': list(
            disposisi.shared_recipients.values_list('role', flat=True)
        ),
    })


@login_required
@require_POST
def share_online_disposisi(request, pk):
    requested_disposisi = get_object_or_404(Disposisi, pk=pk)
    can_share = (
        request.user.can_share_disposisi
        if requested_disposisi.tipe_disposisi == 'ONLINE'
        else request.user.can_edit_disposisi
    )
    if not can_share:
        raise PermissionDenied

    form = ShareDisposisiForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors['recipients'][0])
        return redirect('disposisi:detaildisposisi', pk=pk)

    with transaction.atomic():
        disposisi = get_object_or_404(
            Disposisi.objects.select_for_update(),
            pk=pk,
        )
        if not (
            disposisi.tipe_disposisi in {'ONLINE', 'OFFLINE'}
            and disposisi.status_pengajuan == 'DIISI'
        ):
            messages.error(request, "Disposisi ini belum siap dibagikan.")
            return redirect('disposisi:detaildisposisi', pk=pk)
        can_share_locked = (
            request.user.can_share_disposisi
            if disposisi.tipe_disposisi == 'ONLINE'
            else request.user.can_edit_disposisi
        )
        if not can_share_locked:
            raise PermissionDenied

        selected_roles = form.cleaned_data['recipients']
        disposisi.shared_recipients.all().delete()
        DisposisiRecipient.objects.bulk_create([
            DisposisiRecipient(disposisi=disposisi, role=role)
            for role in selected_roles
        ])
        is_offline = disposisi.tipe_disposisi == 'OFFLINE'
        disposisi.status_pengajuan = 'SELESAI' if is_offline else 'DIBAGIKAN'
        disposisi.save(update_fields=['status_pengajuan', 'waktu_diedit'])

        role_labels = dict(Disposisi.SHARE_ROLE_CHOICES)
        recipient_names = ', '.join(role_labels[role] for role in selected_roles)
        create_log(
            disposisi,
            request.user,
            'BAGI_DISPOSISI',
            f'Disposisi dibagikan kepada: {recipient_names}.',
        )
        if is_offline:
            create_log(
                disposisi,
                request.user,
                'SELESAI',
                'Disposisi offline selesai setelah file diunggah dan dibagikan.',
            )

    if is_offline:
        messages.success(
            request,
            f"Disposisi offline berhasil dibagikan kepada {recipient_names} dan selesai.",
        )
    else:
        messages.success(request, f"Disposisi berhasil dibagikan kepada {recipient_names}.")
    return redirect('disposisi:detaildisposisi', pk=pk)


@login_required
@require_POST
def complete_shared_disposisi(request, pk):
    with transaction.atomic():
        disposisi = get_object_or_404(
            Disposisi.objects.select_for_update(),
            pk=pk,
        )
        recipient = disposisi.shared_recipients.select_for_update().filter(
            role=request.user.role,
        ).first()
        if recipient is None:
            raise PermissionDenied
        if recipient.agreed_at is not None:
            messages.info(request, "Anda sudah menyetujui disposisi ini.")
            return redirect('disposisi:detaildisposisi', pk=pk)
        if not (
            disposisi.tipe_disposisi == 'ONLINE'
            and disposisi.status_pengajuan == 'DIBAGIKAN'
        ):
            messages.error(request, "Disposisi ini tidak dapat diselesaikan.")
            return redirect('disposisi:detaildisposisi', pk=pk)

        recipient.agreed_at = timezone.now()
        recipient.save(update_fields=['agreed_at'])
        create_log(
            disposisi,
            request.user,
            'TERIMA_DISPOSISI',
            f'Disposisi disetujui oleh {request.user.get_role_display()}.',
        )

        is_complete = not disposisi.shared_recipients.filter(
            agreed_at__isnull=True,
        ).exists()
        if is_complete:
            disposisi.status_pengajuan = 'SELESAI'
            disposisi.save(update_fields=['status_pengajuan', 'waktu_diedit'])
            create_log(
                disposisi,
                request.user,
                'SELESAI',
                'Seluruh penerima telah menyetujui disposisi.',
            )

    if is_complete:
        messages.success(request, "Semua penerima telah menyetujui. Disposisi selesai.")
    else:
        messages.success(
            request,
            "Persetujuan berhasil. Menunggu persetujuan penerima lainnya.",
        )
    return redirect('disposisi:detaildisposisi', pk=pk)

@login_required
@disposisi_editor_required
@require_POST
def edit_file_disposisi(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)

    form = DisposisiUploadForm(request.POST, request.FILES, instance=disposisi)
    if form.is_valid():
        disposisi = form.save()
        create_log(disposisi, request.user, 'DIEDIT')
        return redirect('disposisi:detaildisposisi', pk=pk)
    messages.error(request, "File tidak valid.")
    return redirect('disposisi:detaildisposisi', pk=pk)

@login_required
def download_disposisi_pdf(request, pk):
    disposisi = get_object_or_404(Disposisi, pk=pk)

    html_string = render_to_string(
        'disposisi_pdf.html',
        {
            'disposisi': disposisi,
            'selected_recipient_roles': list(
                disposisi.shared_recipients.values_list('role', flat=True)
            ),
        }
    )

    response = HttpResponse(content_type='application/pdf')
    filename = f'Disposisi-{disposisi.nomor_agenda}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/')
    ).write_pdf(response)

    return response
