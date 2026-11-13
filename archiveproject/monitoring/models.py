from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.directory import MEMBER_DIVISION_ORDER


def current_month():
    today = timezone.localdate()
    return today.replace(day=1)


class Assignment(models.Model):
    STATUS_CHOICES = [
        ("todo", "Belum dimulai"),
        ("doing", "Dalam proses"),
        ("done", "Selesai"),
    ]

    title = models.CharField("Tugas", max_length=220)
    description = models.TextField("Deskripsi", blank=True)
    month = models.DateField("Bulan kerja", default=current_month)
    start_date = models.DateField("Tanggal mulai")
    due_date = models.DateField("Tenggat waktu")
    division = models.CharField(
        "Divisi", max_length=120,
        choices=[(name, name) for name in MEMBER_DIVISION_ORDER],
    )
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="monitoring_assignments", verbose_name="Penanggung jawab",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="todo")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="monitoring_created_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "pk"]
        indexes = [models.Index(fields=["month", "division", "status"], name="monitor_month_div_status")]

    def clean(self):
        if self.month and self.month.day != 1:
            raise ValidationError({"month": "Bulan kerja harus dimulai tanggal 1."})
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValidationError({"due_date": "Tenggat tidak boleh sebelum tanggal mulai."})

    @property
    def is_overdue(self):
        return self.status != "done" and self.due_date < timezone.localdate()

    def __str__(self):
        return self.title
