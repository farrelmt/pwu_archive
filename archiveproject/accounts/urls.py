from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('system/<str:system>/', views.system_launch, name='system_launch'),
    path('handoff/', views.system_handoff, name='system_handoff'),


]
