from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = 'homepage'

urlpatterns = [
    path('', views.root, name='dashboard'),
    path('member/', views.member_list, name='member_list'),
    path('member/tambah/', views.member_create, name='member_create'),
    path('member/<int:pk>/edit/', views.member_edit, name='member_edit'),
    path('member/<int:pk>/hapus/', views.member_delete, name='member_delete'),
    path('settings/', views.personal_settings, name='personal_settings'),
    path('nota-dinas/', views.nota_dinas, name='notadinas'),
    path('surat-keluar/', views.surat_keluar, name='suratkeluar'),
    path('inbox/', views.inbox, name='inbox'),
    path('monitor/', views.monitoring, name='monitor'),
    path('divisi/', views.divisi, name='divisi'),
    path('activity-log/', views.activity_log, name='activity_log'),
    path('notif/', views.notifikasi, name='notif'),
    path('report/', views.report, name='report'),

]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )


