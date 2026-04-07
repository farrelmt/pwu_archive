from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = 'pengaturan'

urlpatterns = [
    path('', views.home, name='main'),
    path('edit-profil/<int:pk>/', views.edit_profil, name='edit-profil'),
]