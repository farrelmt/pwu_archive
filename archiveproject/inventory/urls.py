from django.urls import path

from . import views, requests

app_name = "inventory"

urlpatterns = [
    path("permintaan/", requests.request_list, name="request_list"),
    path("permintaan/tambah/", requests.request_create, name="request_new"),
    path("permintaan/<str:public_id>/", requests.request_detail, name="request_detail"),
    path("permintaan/<str:public_id>/unduh/", requests.request_download, name="request_download"),
    path("", views.dashboard, name="dashboard"),
    path("activity-log/", views.activity_log, name="activity_log"),
    path("anggota/", views.member_list, name="member_list"),
    path("anggota/<int:pk>/", views.member_detail, name="member_detail"),
    path("barang/", views.item_list, name="item_list"),
    path("barang/laporan-excel/", views.export_inventory_excel, name="export_inventory_excel"),
    path("barang/tambah/", views.item_create, name="item_create"),
    path("inventaris-saya/", views.my_inventory, name="my_inventory"),
    path("internet/", views.internet_list, name="internet_list"),
    path("internet/<int:pk>/", views.internet_detail, name="internet_detail"),
    path("barang-saya/tambah/", views.personal_item_create, name="personal_item_create"),
    path("barang-saya/<int:pk>/edit/", views.personal_item_edit, name="personal_item_edit"),
    path("barang-saya/<int:pk>/hapus/", views.personal_item_delete, name="personal_item_delete"),
    path("barang/<int:pk>/", views.item_detail, name="item_detail"),
    path("barang/<int:pk>/password/", views.software_password_reveal, name="software_password_reveal"),
    path("barang/<int:pk>/edit/", views.item_edit, name="item_edit"),
    path("barang/<int:pk>/hapus/", views.item_delete, name="item_delete"),
    path("laporan/tambah/", requests.request_create, name="report_new"),
    path("barang/<int:pk>/foto/", views.item_photo, name="item_photo"),
    path("laporan/", requests.request_list, name="report_list"),
    path("laporan/barang/<int:item_pk>/tambah/", requests.request_create, name="report_create"),
    path("laporan/<int:pk>/", views.report_detail, name="report_detail"),
    path("laporan/<int:pk>/lanjutkan/", views.report_advance, name="report_advance"),
]
