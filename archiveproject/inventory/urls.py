from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("anggota/", views.member_list, name="member_list"),
    path("anggota/tambah/", views.member_create, name="member_create"),
    path("anggota/<int:pk>/", views.member_detail, name="member_detail"),
    path("anggota/<int:pk>/edit/", views.member_edit, name="member_edit"),
    path("barang/", views.item_list, name="item_list"),
    path("barang/tambah/", views.item_create, name="item_create"),
    path("barang/<int:pk>/", views.item_detail, name="item_detail"),
    path("barang/<int:pk>/edit/", views.item_edit, name="item_edit"),
]
