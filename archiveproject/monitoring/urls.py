from django.urls import path

from . import views

app_name = "monitoring"

urlpatterns = [
    path("", views.board, name="board"),
    path("tugas/tambah/", views.assignment_create, name="assignment_create"),
    path("tugas/<int:pk>/", views.assignment_detail, name="assignment_detail"),
    path("tugas/<int:pk>/edit/", views.assignment_edit, name="assignment_edit"),
    path("tugas/<int:pk>/status/", views.assignment_status, name="assignment_status"),
]
