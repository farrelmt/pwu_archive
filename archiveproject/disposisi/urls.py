from django.urls import path, register_converter
from . import views
from .converters import EncryptedDisposisiIdConverter
from django.conf import settings
from django.conf.urls.static import static

app_name = 'disposisi'

register_converter(EncryptedDisposisiIdConverter, 'disposisi_id')

urlpatterns = [
    path('', views.list_disposisi, name='disposisi'),
    path('tambah/', views.tambah_disposisi, name='tambahdisposisi'),
    path('<disposisi_id:pk>/', views.detail_disposisi, name='detaildisposisi'),
    path('edit/<disposisi_id:pk>/', views.update_disposisi, name='editdisposisi'),
    path('hapus/<disposisi_id:pk>/', views.hapus_disposisi, name='hapusdisposisi'),
    path('preview/<disposisi_id:pk>/', views.preview_disposisi, name='previewdisposisi'),
    path('preview/<disposisi_id:pk>/pdf/', views.download_disposisi_pdf, name='disposisi_pdf'),
    path(
        '<disposisi_id:pk>/document/<str:kind>/',
        views.download_document,
        name='download_document',
    ),
    path('<disposisi_id:pk>/upload/', views.upload_disposisi, name='uploaddisposisi'),
    path('<disposisi_id:pk>/online/cancel/', views.cancel_online_disposisi, name='cancelonline'),
    path('<disposisi_id:pk>/online/decision/', views.decide_online_disposisi, name='decisiononline'),
    path('<disposisi_id:pk>/online/isi/', views.isi_online_disposisi, name='isionline'),
    path('<disposisi_id:pk>/online/share/', views.share_online_disposisi, name='shareonline'),
    path('<disposisi_id:pk>/online/complete/', views.complete_shared_disposisi, name='completeonline'),
]
