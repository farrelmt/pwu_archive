from django.urls import path
from . import views

app_name = 'disposisi'

urlpatterns = [
    path('', views.list_disposisi, name='disposisi'),
    path('tambah/', views.tambah_disposisi, name='tambahdisposisi'),
    path('filter/', views.filter_disposisi, name='filterdisposisi'),
    path('<int:pk>/', views.tambah_disposisi, name='detaildisposisi'),
    path('edit/<int:pk>/', views.update_disposisi, name='editdisposisi'),
    path('hapus/<int:pk>/', views.tambah_disposisi, name='hapusdisposisi'),
]

