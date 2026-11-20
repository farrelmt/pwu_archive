from django.urls import path

from . import views

app_name = "monitoring"

urlpatterns = [
    path("", views.board, name="board"),
    path("tugas/daftar/", views.assignment_list, name="assignment_list"),
    path("tugas/tambah/", views.assignment_create, name="assignment_create"),
    path("tugas/<uuid:public_id>/", views.assignment_detail, name="assignment_detail"),
    path("tugas/<uuid:public_id>/edit/", views.assignment_edit, name="assignment_edit"),
    path("tugas/<uuid:public_id>/hapus/", views.assignment_delete, name="assignment_delete"),
    path("tugas/<uuid:public_id>/status/", views.assignment_status, name="assignment_status"),
    path("tugas/<uuid:public_id>/checklist/grup/tambah/", views.checklist_group_add, name="checklist_group_add"),
    path("tugas/<uuid:public_id>/checklist/grup/<int:group_pk>/edit/", views.checklist_group_edit, name="checklist_group_edit"),
    path("tugas/<uuid:public_id>/checklist/grup/<int:group_pk>/hapus/", views.checklist_group_delete, name="checklist_group_delete"),
    path("tugas/<uuid:public_id>/checklist/grup/<int:group_pk>/tambah/", views.checklist_add, name="checklist_add"),
    path("tugas/<uuid:public_id>/checklist/<int:item_pk>/toggle/", views.checklist_toggle, name="checklist_toggle"),
    path("tugas/<uuid:public_id>/checklist/<int:item_pk>/edit/", views.checklist_edit, name="checklist_edit"),
    path("tugas/<uuid:public_id>/checklist/<int:item_pk>/hapus/", views.checklist_delete, name="checklist_delete"),
]
