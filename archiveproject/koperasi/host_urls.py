from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("pengaturan/", include("pengaturan.urls")),
    path("", include("koperasi.urls")),
]
