from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('homepage.urls')),
    path('accounts/', include('accounts.urls')),
    path('disposisi/', include('disposisi.urls')),
    path('pengaturan/', include('pengaturan.urls')),
    path("__reload__/", include("django_browser_reload.urls")),
]
