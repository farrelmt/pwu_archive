from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.contrib import messages
from .models import AppSetting
from django.conf import settings
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
