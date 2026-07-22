from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import AppSetting
from django.conf import settings
from .services import monitor_disposisi_for_user
import textwrap

@login_required(login_url='accounts:login')
def dashboard(request):
    links = [
        {"page": "disposisi", "url": "disposisi", "title": "Disposisi", "icon": "disposisi"},
        {"page": "nota_dinas",  "url": "notadinas", "title": "Nota Dinas", "icon": "nota_dinas"},
        {"page": "surat_keluar", "url": "suratkeluar", "title": "Surat Keluar", "icon": "surat_keluar"},
        {"page": "monitor", "url": "monitor", "title": "Monitor", "icon": "monitor"},
        {"page": "divisi", "url": "divisi", "title": "Divisi", "icon": "divisi"},
    ]
    pending_online_count = monitor_disposisi_for_user(request.user).count()
    return render(request, 'dashboard.html', {
        'links': links,
        'pending_online_count': pending_online_count,
    })

@login_required(login_url='accounts:login')
def nota_dinas(request):
    return render(request, 'nota_dinas.html')

@login_required(login_url='accounts:login')
def surat_keluar(request):
    return render(request, 'surat_keluar.html')

@login_required(login_url='accounts:login')
def monitoring(request):
    pending_online = monitor_disposisi_for_user(request.user).order_by('waktu_diedit')

    search = request.GET.get('search', '').strip()
    if search:
        pending_online = pending_online.filter(
            Q(nomor_agenda__icontains=search)
            | Q(nomor_surat__icontains=search)
            | Q(pengirim__icontains=search)
            | Q(perihal__icontains=search)
        )

    try:
        page_limit = int(request.GET.get('limit', 20))
    except (TypeError, ValueError):
        page_limit = 20
    if page_limit not in {20, 50, 100}:
        page_limit = 20

    paginator = Paginator(pending_online, page_limit)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'monitor.html', {
        'page_obj': page_obj,
        'page_limit': str(page_limit),
        'search': search,
    })

@login_required(login_url='accounts:login')
def divisi(request):
    users = get_user_model().objects.all().order_by('role', 'username')
    return render(request, 'divisi.html', {'users': users})

@login_required(login_url='accounts:login')
def notifikasi(request):
    messages.info(request, "Fitur notifikasi belum tersedia.")
    return redirect("homepage:dashboard")

@login_required(login_url='accounts:login')
def report(request):
    to_email = settings.EMAIL_TO_REPORT

    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")
        steps = request.POST.get("steps")
        screenshot = request.FILES.get("screenshot")

        user = request.user

        email_body = textwrap.dedent(f"""
BUG REPORT 

User: {user.username}
Email: {user.email}

Title: {title}

Description: 
{description}

Steps: 
{steps}
        """).strip()

        email = EmailMessage(
            subject=f"Report Bug {title} from PWU ARCHIVE",
            body=email_body,
            to=[to_email],
        )

        if screenshot:
            email.attach(screenshot.name, screenshot.read(), screenshot.content_type)

        email.send()

        messages.success(request, "Report sent successfully")
        return redirect("homepage:dashboard")

    return render(request, 'report.html')
