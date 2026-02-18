from django.db import models, transaction
from django.db.models import Max
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
        nomor_surat = nomor_surat.replace("/", "_")
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
    tujuan_disposisi = models.CharField(max_length=50)
    status_pengajuan = models.CharField(max_length=10, choices=STATUS_CHOICES, default="BELUM")
    dokumen_surat_masuk = models.FileField(
        upload_to= rename_dokumen_surat,
        validators = [FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])]
    )

    waktu_dibuat = models.DateTimeField(auto_now_add=True)
    waktu_diedit = models.DateTimeField(auto_now=True)

    def name_dokumen_surat_masuk(self):
        filename = os.path.basename(self.dokumen_surat_masuk.name)
        return filename.replace("_", "/")

    def save(self, *args, **kwargs):
        is_create = self.pk is None

        with transaction.atomic():
            super().save(*args, **kwargs)
            if not is_create:
                return

            disposisi_list = Disposisi.objects.all().order_by(
                'tanggal_surat_diterima',
                'waktu_dibuat',
                'pk'
            )

            for index, item in enumerate(disposisi_list, start=1):
                if item.id_agenda != index:
                    Disposisi.objects.filter(pk=item.pk).update(id_agenda=index)

        old = None
        if self.pk:
            try:
                old = Disposisi.objects.get(pk=self.pk)
            except Disposisi.DoesNotExist:
                old = None

        if old and old.dokumen_surat_masuk != self.dokumen_surat_masuk:
            if old.dokumen_surat_masuk:
                if os.path.isfile(old.dokumen_surat_masuk.path):
                    os.remove(old.dokumen_surat_masuk.path)


    def __str__(self):
        return f"{self.nomor_surat} - {self.perihal[:30]}"
