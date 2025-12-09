from django.db import models

class Disposisi(models.Model):

    TUJUAN_CHOICES = [
        ("DIRUT", "Direktur Utama"),
        ("DIR", "Direktur"),
    ]

    tanggal_surat_diterima = models.DateField()
    nomor_agenda = models.CharField(max_length=20)
    tanggal_surat = models.DateField()
    nomor_surat = models.CharField(max_length=50)
    pengirim = models.CharField(max_length=50)
    lampiran = models.CharField(max_length=50)
    tujuan = models.CharField(max_length=20, choices=TUJUAN_CHOICES)
    tembusan = models.CharField(max_length=50)
    perihal = models.TextField()
    diajukan_kepada = models.CharField(max_length=20, choices=TUJUAN_CHOICES)
    dokumen_surat_masuk = models.CharField(max_length=100, default="N/A")

    waktu_dibuat = models.DateTimeField(auto_now_add=True)
    waktu_diedit = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nomor_surat} - {self.perihal[:30]}"
