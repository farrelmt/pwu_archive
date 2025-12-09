from django.contrib import admin
from .models import Disposisi

@admin.register(Disposisi)
class DisposisiAdmin(admin.ModelAdmin):
    list_display = (
        "nomor_surat", "pengirim", "tujuan",
        "diajukan_kepada", "tanggal_surat", "waktu_dibuat"
    )
    search_fields = ("nomor_surat", "pengirim", "perihal")
    list_filter = ("tujuan", "diajukan_kepada", "tanggal_surat")
