from django.db import models, transaction
from django.db.models import Max
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils.text import slugify
import os

class Disposisi(models.Model):
    TIPE_CHOICES = [
        ('BELUM', 'Metode Belum Dipilih'),
        ('ONLINE', 'Disposisi Online'),
        ('OFFLINE', 'Upload Disposisi Fisik (Offline)'),
    ]
    tipe_disposisi = models.CharField(max_length=10, choices=TIPE_CHOICES, default='BELUM')

    TUJUAN_CHOICES = [
        ("DIRUT", "Direktur Utama"),
        ("DIR", "Direktur"),
        ("DIREKSI", "Direksi"),
    ]

    STATUS_CHOICES = [
        ("DIBUAT", "Disposisi Telah Dibuat"),
        ("DIAJUKAN", "Disposisi Telah Diajukan"),
        ("DIISI", "Disposisi Telah Diisi"),
        ("DIBAGIKAN", "Disposisi Telah Dibagikan"),
        ("VERIFIKASI", "Menunggu Persetujuan Sekretaris"),
        ("SELESAI", "Disposisi Telah Selesai"),
    ]

    SHARE_ROLE_CHOICES = [
        ('direktur_utama', 'Direktur Utama'),
        ('direktur', 'Direktur'),
        ('direktur_umum', 'Direktur'),
        ('kadiv_akuntansi', 'Kepala Divisi Akuntansi'),
        ('kadiv_keuangan', 'Kepala Divisi Keuangan'),
        ('kadiv_risiko', 'Kepala Divisi Manajemen Risiko'),
        ('kadiv_legal_umum', 'Kepala Divisi Legal dan Umum'),
        ('kadiv_aset', 'Kepala Divisi Aset'),
        ('kadiv_spi', 'Kepala SPI'),
        ('wirajatim_kso', 'Wirajatim KSO'),
    ]
    ONLINE_SHARE_ROLE_CHOICES = [
        ('direktur_utama', 'Direktur Utama'),
        ('direktur_umum', 'Direktur'),
        ('kadiv_akuntansi', 'Kepala Divisi Akuntansi'),
        ('kadiv_keuangan', 'Kepala Divisi Keuangan'),
        ('kadiv_risiko', 'Kepala Divisi Manajemen Risiko'),
        ('kadiv_legal_umum', 'Kepala Divisi Legal dan Umum'),
        ('kadiv_aset', 'Kepala Divisi Aset'),
        ('kadiv_spi', 'Kepala SPI'),
        ('wirajatim_kso', 'Wirajatim KSO'),
    ]
    OFFLINE_SHARE_ROLE_CHOICES = [
        ('direktur_utama', 'Direktur Utama'),
        ('direktur_umum', 'Direktur'),
        ('kadiv_akuntansi', 'Kepala Divisi Akuntansi'),
        ('kadiv_keuangan', 'Kepala Divisi Keuangan'),
        ('kadiv_risiko', 'Kepala Divisi Manajemen Risiko'),
        ('kadiv_legal_umum', 'Kepala Divisi Legal dan Umum'),
        ('kadiv_aset', 'Kepala Divisi Aset'),
        ('kadiv_spi', 'Kepala SPI'),
        ('wirajatim_kso', 'Wirajatim KSO'),
    ]
    INFORMATIONAL_RECIPIENT_ROLES = frozenset({
        'direktur_utama',
        'direktur',
        'direktur_umum',
        'kadiv_spi',
    })

    BULAN_ROMAWI = ['', 'I', 'II', 'III', 'IV', 'V', 'VI',
                    'VII', 'VIII', 'IX', 'X', 'XI', 'XII']

    def rename_dokumen_surat(instance, filename):
        extension = os.path.splitext(filename)[1]
        tahun = instance.tanggal_surat_diterima.strftime("%Y")
        nomor_agenda = instance.nomor_agenda.replace("/", "-")
        nomor_surat = instance.nomor_surat.replace("/", "_")
        pk = instance.pk

        return f"Disposisi/{tahun}/{pk}/Surat Masuk/{nomor_surat}{extension}"

    def rename_dokumen_disposisi(instance, filename):
        extension = os.path.splitext(filename)[1]
        tahun = instance.tanggal_surat_diterima.strftime("%Y")
        nomor_agenda = instance.nomor_agenda.replace("/", "-")
        nomor_surat = instance.nomor_surat.replace("/", "_")
        pk = instance.pk

        return f"Disposisi/{tahun}/{pk}/Disposisi/{nomor_surat}{extension}"

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
    isi_disposisi = models.TextField(blank=True, default='')
    isi_disposisi_dirut = models.TextField(blank=True, default='')
    isi_disposisi_direktur = models.TextField(blank=True, default='')
    status_pengajuan = models.CharField(max_length=10, choices=STATUS_CHOICES, default="DIBUAT")
    deadline = models.DateField(blank=True, null=True)

    dokumen_surat_masuk = models.FileField(
        upload_to= rename_dokumen_surat,
        validators = [FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])]
    )
    dokumen_disposisi = models.FileField(
        upload_to= rename_dokumen_disposisi,
        validators = [FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        blank=True,
        null=True
    )

    waktu_dibuat = models.DateTimeField(auto_now_add=True)
    waktu_diedit = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=['-tanggal_surat_diterima', '-id'],
                name='disp_received_pk_idx',
            ),
            models.Index(
                fields=['tipe_disposisi', 'status_pengajuan'],
                name='disp_type_status_idx',
            ),
            models.Index(
                fields=['tujuan', 'status_pengajuan'],
                name='disp_target_status_idx',
            ),
            models.Index(
                fields=['status_pengajuan', 'deadline'],
                name='disp_status_deadline_idx',
            ),
        ]

    def name_dokumen_surat_masuk(self):
        filename = os.path.basename(self.dokumen_surat_masuk.name)
        return filename.replace("_", "/")

    def clean(self):
        super().clean()
        if (
            self.tanggal_surat_diterima
            and self.tanggal_surat
            and self.tanggal_surat_diterima < self.tanggal_surat
        ):
            raise ValidationError({
                'tanggal_surat_diterima': (
                    'Tanggal surat diterima tidak boleh lebih lama dari tanggal surat.'
                )
            })

    def assign_initial_agenda_number(self):
        """Assign only this new record without renumbering existing records."""
        received_date = self.tanggal_surat_diterima
        earlier_date_count = (
            Disposisi.objects.filter(
                tanggal_surat_diterima__year=received_date.year,
                tanggal_surat_diterima__lt=received_date,
            )
            .values('tanggal_surat_diterima')
            .distinct()
            .count()
        )
        same_date_count = Disposisi.objects.filter(
            tanggal_surat_diterima=received_date,
        ).exclude(pk=self.pk).count()

        base_number = earlier_date_count + 1
        id_agenda_value = (
            str(base_number)
            if same_date_count == 0
            else f'{base_number}.{same_date_count}'
        )
        nomor_agenda_value = (
            f'{id_agenda_value}/{self.BULAN_ROMAWI[received_date.month]}/'
            f'{received_date.year}'
        )
        Disposisi.objects.filter(pk=self.pk).update(
            id_agenda=id_agenda_value,
            nomor_agenda=nomor_agenda_value,
        )
        self.id_agenda = id_agenda_value
        self.nomor_agenda = nomor_agenda_value

    @classmethod
    def refresh_agenda_numbers(cls):
        """Recalculate every agenda number in one explicit bulk operation."""
        all_disposisi = list(
            cls.objects.only(
                'pk', 'tanggal_surat_diterima', 'id_agenda', 'nomor_agenda',
            ).order_by('tanggal_surat_diterima', 'pk')
        )
        base_number = 0
        current_date = None
        current_year = None
        sub_count = 0
        changed = []

        for disposisi in all_disposisi:
            received_date = disposisi.tanggal_surat_diterima
            if received_date.year != current_year:
                base_number = 0
                current_year = received_date.year
                current_date = None
                sub_count = 0

            if received_date != current_date:
                base_number += 1
                current_date = received_date
                sub_count = 0
                id_agenda_value = str(base_number)
            else:
                sub_count += 1
                id_agenda_value = f'{base_number}.{sub_count}'

            nomor_agenda_value = (
                f'{id_agenda_value}/{cls.BULAN_ROMAWI[received_date.month]}/'
                f'{received_date.year}'
            )
            if (
                disposisi.id_agenda != id_agenda_value
                or disposisi.nomor_agenda != nomor_agenda_value
            ):
                disposisi.id_agenda = id_agenda_value
                disposisi.nomor_agenda = nomor_agenda_value
                changed.append(disposisi)

        if changed:
            cls.objects.bulk_update(
                changed,
                ['id_agenda', 'nomor_agenda'],
                batch_size=500,
            )
        return len(changed)

    def save(self, *args, **kwargs):
        is_create = self.pk is None

        old = None
        if self.pk:
            try:
                old = Disposisi.objects.get(pk=self.pk)
            except Disposisi.DoesNotExist:
                old = None

        if is_create:
            file_surat = self.dokumen_surat_masuk
            file_disposisi = self.dokumen_disposisi

            self.dokumen_surat_masuk = None
            self.dokumen_disposisi = None

            with transaction.atomic():
                super().save(*args, **kwargs)  # pk assigned here

                # Now save with file using the correct pk path
                self.dokumen_surat_masuk = file_surat
                self.dokumen_disposisi = file_disposisi
                super().save(update_fields=['dokumen_surat_masuk', 'dokumen_disposisi'])

        else:
            with transaction.atomic():
                super().save(*args, **kwargs)

            if old and old.dokumen_surat_masuk != self.dokumen_surat_masuk:
                if old.dokumen_surat_masuk:
                    old.dokumen_surat_masuk.storage.delete(
                        old.dokumen_surat_masuk.name
                    )

            if old and old.dokumen_disposisi != self.dokumen_disposisi:
                if old.dokumen_disposisi:
                    old.dokumen_disposisi.storage.delete(
                        old.dokumen_disposisi.name
                    )

        if is_create:
            self.assign_initial_agenda_number()

    def __str__(self):
        return f"{self.nomor_surat} ({self.nomor_agenda})"

    def can_be_approved_by(self, user):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if self.tujuan == 'DIRUT':
            return user.role == 'direktur_utama'
        if self.tujuan == 'DIR':
            return user.role in {'direktur', 'direktur_umum'}
        if self.tujuan == 'DIREKSI':
            return user.role in {
                'direktur_utama',
                'direktur',
                'direktur_umum',
            }
        return False

    def can_fill_online_disposition(self, user):
        """Return whether ``user`` owns the currently active online stage."""
        if not user.is_authenticated:
            return False
        if not (
            self.tipe_disposisi == 'ONLINE'
            and self.status_pengajuan == 'DIAJUKAN'
        ):
            return False
        if self.tujuan != 'DIREKSI':
            return self.can_be_approved_by(user)

        if not self.isi_disposisi_dirut:
            return user.is_superuser or user.role == 'direktur_utama'
        if not self.isi_disposisi_direktur:
            return user.is_superuser or user.role in {
                'direktur', 'direktur_umum',
            }
        return False

    def online_input_stage_for(self, user):
        """Identify the field and label for the active director stage."""
        if not self.can_fill_online_disposition(user):
            return None
        if self.tujuan != 'DIREKSI':
            return 'isi_disposisi', self.get_tujuan_display()
        if not self.isi_disposisi_dirut:
            return 'isi_disposisi_dirut', 'Direktur Utama'
        return 'isi_disposisi_direktur', 'Direktur'

    @property
    def direksi_input_complete(self):
        return bool(
            self.isi_disposisi_dirut and self.isi_disposisi_direktur
        )


class DisposisiRecipient(models.Model):
    disposisi = models.ForeignKey(
        Disposisi,
        on_delete=models.CASCADE,
        related_name='shared_recipients',
    )
    role = models.CharField(max_length=30, choices=Disposisi.SHARE_ROLE_CHOICES)
    received_at = models.DateTimeField(blank=True, null=True)
    agreed_at = models.DateTimeField(blank=True, null=True)
    activity_description = models.TextField(blank=True, default='')
    follow_up_result = models.TextField(blank=True, default='')
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='completed_disposisi_recipients',
    )

    @property
    def requires_action(self):
        return self.role not in Disposisi.INFORMATIONAL_RECIPIENT_ROLES

    class Meta:
        ordering = ['role']
        constraints = [
            models.UniqueConstraint(
                fields=['disposisi', 'role'],
                name='unique_disposisi_recipient_role',
            ),
        ]

    def __str__(self):
        return f"{self.disposisi.nomor_agenda} - {self.get_role_display()}"


class DisposisiLog(models.Model):
    ACTION_CHOICES = [
        ('DIBUAT', 'Telah Dibuat'),
        ('DIEDIT', 'Telah Diedit'),
        ('UPLOAD_DISPOSISI', 'File Telah Di Upload'),
        ('AJUKAN_DISPOSISI', 'Diajukan'),
        ('BATAL_PENGAJUAN', 'Pengajuan Dibatalkan'),
        ('TOLAK_DISPOSISI', 'Pengajuan Ditolak'),
        ('SETUJUI_DISPOSISI', 'Pengajuan Disetujui'),
        ('ISI_DISPOSISI', 'Diisi'),
        ('BAGI_DISPOSISI', 'Dibagi'),
        ('TERIMA_DISPOSISI', 'Diterima Penerima'),
        ('AKTIVITAS_PENERIMA', 'Aktivitas Penerima'),
        ('AJUKAN_SELESAI', 'Diajukan ke Sekretaris'),
        ('SELESAI', 'Selesai'),
    ]

    disposisi = models.ForeignKey(Disposisi, on_delete=models.CASCADE, related_name='logs')
    user_log = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='userlog' )
    action_log = models.CharField(max_length=20, choices=ACTION_CHOICES, default='DIBUAT')
    keterangan_log = models.TextField(blank=True)
    waktu = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-waktu']

    def __str__(self):
        return f"{self.disposisi.nomor_surat} - {self.action_log}"
