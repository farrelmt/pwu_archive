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

    BULAN_ROMAWI = ['', 'I', 'II', 'III', 'IV', 'V', 'VI',
                    'VII', 'VIII', 'IX', 'X', 'XI', 'XII']


    def rename_dokumen_surat(instance, filename):
        extension = os.path.splitext(filename)[1]
        tahun = instance.tanggal_surat_diterima.strftime("%Y")
        nomor_agenda = instance.nomor_agenda.replace("/", "-")
        nomor_surat = instance.nomor_surat.replace("/", "_")

        return f"Disposisi/{tahun}/{nomor_agenda}/Surat Masuk/{nomor_surat}{extension}"

    tanggal_surat_diterima = models.DateField()
    id_agenda = models.CharField(max_length=20, blank=True, null=True)
    nomor_agenda = models.CharField(max_length=20, blank=True, default='')
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

    def reassign_agenda_number(self):
        all_disposisi = Disposisi.objects.all().order_by('tanggal_surat_diterima', 'pk')

        base_number = 0
        current_date = None
        current_year = None
        sub_count = 0

        for d in all_disposisi:
            date = d.tanggal_surat_diterima

            if date.year != current_year:
                base_number = 0
                current_year = date.year
                current_date = None
                sub_count = 0

            if date != current_date:
                base_number += 1
                current_date = date
                sub_count = 0
                id_agenda_value = str(base_number)

            else:
                sub_count += 1
                id_agenda_value = f"{base_number}.{sub_count}"

            month = date.month
            year = date.year
            new_nomor_agenda = f"{id_agenda_value}/{Disposisi.BULAN_ROMAWI[month]}/{year}"

            Disposisi.objects.filter(pk=d.pk).update(
                id_agenda=id_agenda_value,
                nomor_agenda=new_nomor_agenda,
        )

    def save(self, *args, **kwargs):
        is_create = self.pk is None

        old = None
        if self.pk:
            try:
                old = Disposisi.objects.get(pk=self.pk)
            except Disposisi.DoesNotExist:
                old = None

        with transaction.atomic():
            super().save(*args, **kwargs)
            if not is_create:
                return

        if old and old.dokumen_surat_masuk != self.dokumen_surat_masuk:
            if old.dokumen_surat_masuk:
                if os.path.isfile(old.dokumen_surat_masuk.path):
                    os.remove(old.dokumen_surat_masuk.path)

        self.reassign_agenda_number()

    def __str__(self):
        return f"{self.nomor_surat} - {self.perihal[:30]}"

