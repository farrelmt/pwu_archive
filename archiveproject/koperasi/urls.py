from django.urls import path

from . import views


app_name = "koperasi"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("perusahaan/", views.company_list, name="companies"),
    path("perusahaan/tambah/", views.company_create, name="company_create"),
    path("perusahaan/<int:pk>/edit/", views.company_edit, name="company_edit"),
    path("anggota/", views.member_list, name="members"),
    path("anggota/tambah/", views.member_create, name="member_create"),
    path("anggota/<int:pk>/", views.member_detail, name="member_detail"),
    path("anggota/<int:pk>/edit/", views.member_edit, name="member_edit"),
    path("simpanan/", views.saving_list, name="savings"),
    path("simpanan/tambah/", views.saving_create, name="saving_create"),
    path("pinjaman/", views.loan_list, name="loans"),
    path("pinjaman/tambah/", views.loan_create, name="loan_create"),
    path("pinjaman/<int:pk>/", views.loan_detail, name="loan_detail"),
    path(
        "pinjaman/<int:pk>/status/<str:action>/",
        views.loan_status,
        name="loan_status",
    ),
    path(
        "pinjaman/<int:pk>/angsuran/",
        views.installment_create,
        name="installment_create",
    ),
    path("kas/", views.cash_list, name="cash"),
    path("kas/tambah/", views.cash_create, name="cash_create"),
    path("akses/", views.access_list, name="access"),
    path("akses/tambah/", views.access_create, name="access_create"),
    path("laporan/", views.report, name="report"),
    path("laporan/csv/", views.report_csv, name="report_csv"),
]

