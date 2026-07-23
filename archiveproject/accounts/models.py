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


class ActivityLog(models.Model):
    CATEGORY_CHOICES = [
        ('AUTH', 'Authentication'),
        ('DISPOSISI', 'Disposisi'),
        ('ACCOUNT', 'Account'),
        ('SYSTEM', 'System'),
    ]

    actor = models.ForeignKey(
        SystemUser,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='activity_logs',
    )
    actor_username = models.CharField(max_length=150, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    action = models.CharField(max_length=64)
    description = models.TextField(blank=True)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    target_label = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(blank=True, default=dict)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=512, blank=True)
    success = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        indexes = [
            models.Index(fields=['created_at'], name='activity_created_idx'),
            models.Index(fields=['actor', 'created_at'], name='activity_actor_idx'),
            models.Index(fields=['category', 'action'], name='activity_action_idx'),
        ]

    def __str__(self):
        actor = self.actor_username or 'Anonymous'
        return f'{actor} - {self.action} - {self.created_at:%Y-%m-%d %H:%M}'
