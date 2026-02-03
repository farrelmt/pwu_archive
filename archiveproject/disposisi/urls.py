from django.urls import path
from . import views

app_name = 'disposisi'

urlpatterns = [
    path('', views.list_disposisi, name='disposisi'),
    path('tambah/', views.tambah_disposisi, name='tambahdisposisi'),
    path('<int:pk>/', views.detail_disposisi, name='detaildisposisi'),
    path('edit/<int:pk>/', views.update_disposisi, name='editdisposisi'),
    path('hapus/<int:pk>/', views.hapus_disposisi, name='hapusdisposisi'),
]

