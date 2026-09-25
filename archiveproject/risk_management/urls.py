from django.urls import path

from . import views

app_name = "risk"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("risiko/", views.risk_list, name="risk_list"),
    path("risiko/tambah/", views.risk_create, name="risk_create"),
    path("risiko/<int:pk>/", views.risk_detail, name="risk_detail"),
    path("risiko/<int:pk>/edit/", views.risk_edit, name="risk_edit"),
    path("risiko/<int:risk_pk>/pemantauan/tambah/", views.monitoring_create, name="monitoring_create"),
    path("pemantauan/<int:pk>/edit/", views.monitoring_edit, name="monitoring_edit"),
    path("pemantauan/<int:monitoring_pk>/aksi/tambah/", views.action_create, name="action_create"),
    path("aksi/<int:pk>/edit/", views.action_edit, name="action_edit"),
    path("pemantauan/", views.monitoring_report, name="monitoring_report"),
    path("divisi/", views.divisions, name="divisions"),
]
