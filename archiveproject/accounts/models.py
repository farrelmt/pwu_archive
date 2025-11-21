from django.db import models
from django.contrib.auth.models import AbstractUser

class SystemUser(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)

    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('sekretaris', 'Sekretaris'),
        ('kadiv', 'Kepala Divisi'),
        ('direktur', 'Direktur'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'