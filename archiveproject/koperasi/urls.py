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
    path("anggota/<int:pk>/hapus/", views.member_delete, name="member_delete"),
    path(
        "anggota/<int:pk>/status/<str:action>/",
        views.member_status,
        name="member_status",
    ),
    path("simpanan/", views.saving_list, name="savings"),
    path("simpanan/tambah/", views.saving_create, name="saving_create"),
    path("simpanan/<int:pk>/", views.saving_detail, name="saving_detail"),
    path("simpanan/<int:pk>/edit/", views.saving_edit, name="saving_edit"),
    path("simpanan/<int:pk>/hapus/", views.saving_delete, name="saving_delete"),
    path("pinjaman/", views.loan_list, name="loans"),
    path("pinjaman/tambah/", views.loan_create, name="loan_create"),
    path("pinjaman/<int:pk>/", views.loan_detail, name="loan_detail"),
    path("pinjaman/<int:pk>/buku/", views.loan_book, name="loan_book"),
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
    path("kas/<int:pk>/", views.cash_detail, name="cash_detail"),
    path(
        "kas/bukti/<str:source_type>/<int:pk>/",
        views.cash_voucher,
        name="cash_voucher",
    ),
    path("potongan-payroll/", views.payroll_list, name="payroll"),
    path("potongan-payroll/tambah/", views.payroll_create, name="payroll_create"),
    path(
        "potongan-payroll/<int:pk>/bukukan/",
        views.payroll_post,
        name="payroll_post",
    ),
    path("sie-usaha/", views.business_list, name="business"),
    path("sie-usaha/tambah/", views.business_create, name="business_create"),
    path(
        "sie-usaha/<int:pk>/status/<str:action>/",
        views.business_status,
        name="business_status",
    ),
    path("akses/", views.access_list, name="access"),
    path("akses/tambah/", views.access_create, name="access_create"),
    path("laporan/", views.report, name="report"),
    path("laporan/csv/", views.report_csv, name="report_csv"),
    path("report/", views.bug_report, name="bug_report"),
]
