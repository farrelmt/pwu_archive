from django.db import models
from django.core.validators import FileExtensionValidator
import os
from django.utils.text import slugify

class Disposisi(models.Model):

    TUJUAN_CHOICES = [
        ("DIRUT", "Direktur Utama"),
        ("DIR", "Direktur"),
    ]

    STATUS_CHOICES = [
        ("BELUM", "Belum Selesai"),
        ("SUDAH", "Sudah Selesai"),
    ]

    def rename_dokumen_surat(instance, filename):
        extension = os.path.splitext(filename)[1]
        tahun = instance.tanggal_surat_diterima.strftime("%Y")
        nomor_surat = instance.nomor_surat
        nomor_agenda = instance.nomor_agenda
        nomor_surat = nomor_surat.replace("/", "-")
        nomor_agenda = nomor_agenda.replace("/", "-")
        return f"Disposisi/{tahun}/{nomor_agenda}/Surat Masuk/{nomor_surat}{extension}"

    tanggal_surat_diterima = models.DateField()
    id_agenda = models.PositiveIntegerField(blank=True, null=True)
    nomor_agenda = models.CharField(max_length=20)
    tanggal_surat = models.DateField()
    nomor_surat = models.CharField(max_length=50)
    pengirim = models.CharField(max_length=50)
    lampiran = models.CharField(max_length=50)
    tujuan = models.CharField(max_length=20, choices=TUJUAN_CHOICES)
    tembusan = models.CharField(max_length=50)
    perihal = models.TextField()
    status_pengajuan = models.CharField(max_length=10, choices=STATUS_CHOICES, default="BELUM")
    dokumen_surat_masuk = models.FileField(
        upload_to= rename_dokumen_surat,
        validators = [FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])]
    )

    waktu_dibuat = models.DateTimeField(auto_now_add=True)
    waktu_diedit = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"{self.nomor_surat} - {self.perihal[:30]}"
