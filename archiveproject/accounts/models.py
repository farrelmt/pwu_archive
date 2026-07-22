from django.db import models
from django.contrib.auth.models import AbstractUser

class SystemUser(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)

    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('sekretaris', 'Sekretaris'),
        ('kadiv', 'Kepala Divisi'),
        ('direktur', 'Direktur'),
        ('direktur_utama', 'Direktur Utama'),
        ('direktur_umum', 'Direktur Umum'),
        ('kadiv_akuntansi', 'Kepala Divisi Akuntansi'),
        ('kadiv_keuangan', 'Kepala Divisi Keuangan'),
        ('kadiv_risiko', 'Kepala Divisi Manajemen Risiko'),
        ('kadiv_legal_umum', 'Kepala Divisi Legal dan Umum'),
        ('kadiv_aset', 'Kepala Divisi Aset'),
        ('kadiv_spi', 'Kepala Divisi SPI'),
    ]

    role = models.CharField(max_length=30, choices=ROLE_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def can_edit_disposisi(self):
        return self.is_superuser or self.role in {'admin', 'sekretaris'}

    @property
    def can_approve_disposisi(self):
        return self.is_superuser or self.role in {
            'direktur',
            'direktur_utama',
            'direktur_umum',
        }

    @property
    def can_share_disposisi(self):
        return self.is_superuser or self.role == 'sekretaris'

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'
