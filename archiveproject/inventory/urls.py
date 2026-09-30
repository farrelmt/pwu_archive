from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("activity-log/", views.activity_log, name="activity_log"),
    path("anggota/", views.member_list, name="member_list"),
    path("anggota/<int:pk>/", views.member_detail, name="member_detail"),
    path("barang/", views.item_list, name="item_list"),
    path("barang/tambah/", views.item_create, name="item_create"),
    path("inventaris-saya/", views.my_inventory, name="my_inventory"),
    path("barang-saya/tambah/", views.personal_item_create, name="personal_item_create"),
    path("barang/<int:pk>/", views.item_detail, name="item_detail"),
    path("barang/<int:pk>/edit/", views.item_edit, name="item_edit"),
    path("laporan/tambah/", views.report_create, name="report_new"),
    path("barang/<int:pk>/foto/", views.item_photo, name="item_photo"),
    path("laporan/", views.report_list, name="report_list"),
    path("laporan/barang/<int:item_pk>/tambah/", views.report_create, name="report_create"),
    path("laporan/<int:pk>/", views.report_detail, name="report_detail"),
    path("laporan/<int:pk>/lanjutkan/", views.report_advance, name="report_advance"),
]
