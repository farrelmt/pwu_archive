from django.urls import path
from . import views

app_name = 'homepage'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('disposisi', views.disposisi, name='disposisi'),
    path('notadinas', views.nota_dinas, name='notadinas'),
    path('suratkeluar', views.surat_keluar, name='suratkeluar'),
    path('monitor', views.monitoring, name='monitor'),
    path('divisi', views.divisi, name='divisi'),
    path('pengaturan', views.pengaturan, name='pengaturan'),
    path('notif', views.notifikasi, name='notif'),
]
