from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = 'homepage'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('nota-dinas/', views.nota_dinas, name='notadinas'),
    path('surat-keluar/', views.surat_keluar, name='suratkeluar'),
    path('monitor/', views.monitoring, name='monitor'),
    path('divisi/', views.divisi, name='divisi'),
    path('notif/', views.notifikasi, name='notif'),
    path('report/', views.report, name='report'),

]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )


