"""End-to-end HTTP workflow for an online incoming-letter disposition."""

from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import ActivityLog, SystemUser
from .models import Disposisi


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class IncomingLetterDireksiWorkflowTests(TestCase):
    def setUp(self):
        self.secretary = SystemUser.objects.create_user(
            username="e2e-secretary", password="test-password", role="sekretaris"
        )
        self.dirut = SystemUser.objects.create_user(
            username="e2e-dirut", password="test-password", role="direktur_utama"
        )
        self.director = SystemUser.objects.create_user(
            username="e2e-director", password="test-password", role="direktur_umum"
        )
        self.accounting = SystemUser.objects.create_user(
            username="e2e-accounting", password="test-password", role="kadiv_akuntansi"
        )
        self.finance = SystemUser.objects.create_user(
            username="e2e-finance", password="test-password", role="kadiv_keuangan"
        )

    def post_as(self, user, name, pk=None, data=None):
        self.client.force_login(user)
        url = reverse("disposisi:" + name, args=[pk] if pk is not None else [])
        return self.client.post(url, data or {})

    def test_secretary_to_direksi_to_recipients_to_done(self):
        received = timezone.localdate()
        created_response = self.post_as(
            self.secretary,
            "tambahdisposisi",
            data={
                "tanggal_surat_diterima": received.isoformat(),
                "tanggal_surat": (received - timedelta(days=1)).isoformat(),
                "nomor_surat": "E2E/DIREKSI/001",
                "pengirim": "Pengirim uji",
                "lampiran": "1",
                "tujuan": "DIREKSI",
                "tembusan": "-",
                "perihal": "Uji alur surat masuk sampai selesai",
                "dokumen_surat_masuk": SimpleUploadedFile(
                    "surat-uji.pdf", b"%PDF-1.4 test", content_type="application/pdf"
                ),
            },
        )
        disposition = Disposisi.objects.get(nomor_surat="E2E/DIREKSI/001")
        pk = disposition.pk
        detail_url = reverse("disposisi:detaildisposisi", args=[pk])
        self.assertRedirects(created_response, detail_url)
        self.assertEqual(disposition.status_pengajuan, "DIBUAT")
        self.assertTrue(disposition.dokumen_surat_masuk.name)

        self.assertRedirects(
            self.post_as(self.secretary, "uploaddisposisi", pk, {"metode": "ONLINE"}),
            detail_url,
        )
        disposition.refresh_from_db()
        self.assertEqual((disposition.tipe_disposisi, disposition.status_pengajuan), ("ONLINE", "DIAJUKAN"))

        isi_url = reverse("disposisi:isionline", args=[pk])
        self.client.force_login(self.director)
        self.assertEqual(self.client.get(isi_url).status_code, 403)
        self.assertEqual(
            self.post_as(self.secretary, "shareonline", pk, {"recipients": ["kadiv_akuntansi"]}).status_code,
            302,
        )
        disposition.refresh_from_db()
        self.assertEqual(disposition.status_pengajuan, "DIAJUKAN")

        signed_dirut = (
            '<p>Dirut: tindak lanjuti surat masuk.</p>'
            '<svg data-signature-overlay="true" viewBox="0 0 700 200">'
            '<path d="M 20 40 L 90 70"></path></svg>'
        )
        self.assertRedirects(
            self.post_as(self.dirut, "isionline", pk, {"isi_disposisi": signed_dirut}),
            detail_url,
        )
        disposition.refresh_from_db()
        self.assertEqual(disposition.status_pengajuan, "DIAJUKAN")
        self.assertIn("Dirut: tindak lanjuti", disposition.isi_disposisi_dirut)
        self.assertIsNotNone(disposition.dirut_signed_on)
        self.assertEqual(self.post_as(self.director, "isionline", pk, {"isi_disposisi": signed_dirut}).status_code, 403)

        self.assertRedirects(self.post_as(self.secretary, "reviewdirut", pk), detail_url)
        disposition.refresh_from_db()
        self.assertEqual(disposition.dirut_reviewed_by, self.secretary)

        signed_director = (
            '<p>Direktur: Akuntansi dan Keuangan memproses surat.</p>'
            '<svg data-signature-overlay="true" viewBox="0 0 700 200">'
            '<path d="M 30 45 L 100 75"></path></svg>'
        )
        self.assertRedirects(
            self.post_as(self.director, "isionline", pk, {"isi_disposisi": signed_director}),
            detail_url,
        )
        disposition.refresh_from_db()
        self.assertEqual(disposition.status_pengajuan, "DIISI")
        self.assertTrue(disposition.direksi_input_complete)
        self.assertIn("Akuntansi dan Keuangan", disposition.isi_disposisi_direktur)
        self.assertIsNotNone(disposition.direktur_signed_on)

        self.assertRedirects(
            self.post_as(self.secretary, "shareonline", pk, {"recipients": ["kadiv_akuntansi", "kadiv_keuangan"]}),
            detail_url,
        )
        disposition.refresh_from_db()
        self.assertEqual(disposition.status_pengajuan, "DIBAGIKAN")
        self.assertEqual(set(disposition.shared_recipients.values_list("role", flat=True)), {"kadiv_akuntansi", "kadiv_keuangan"})
        self.assertRedirects(self.post_as(self.secretary, "approvecomplete", pk), detail_url)
        disposition.refresh_from_db()
        self.assertEqual(disposition.status_pengajuan, "DIBAGIKAN")

        deadline = (received + timedelta(days=7)).isoformat()
        for user, activity, result in (
            (self.accounting, "Periksa pembukuan.", "Pembukuan diperiksa."),
            (self.finance, "Periksa anggaran.", "Anggaran diperiksa."),
        ):
            self.assertRedirects(self.post_as(user, "receiveonline", pk), detail_url)
            self.assertRedirects(
                self.post_as(user, "completeonline", pk, {
                    "activity_description": activity,
                    "deadline": deadline,
                    "follow_up_result": result,
                }),
                detail_url,
            )
            recipient = disposition.shared_recipients.get(role=user.role)
            self.assertIsNotNone(recipient.received_at)
            self.assertIsNotNone(recipient.agreed_at)
            self.assertEqual(recipient.completed_by, user)
            self.assertEqual(recipient.follow_up_result, result)
            disposition.refresh_from_db()
            self.assertEqual(
                disposition.status_pengajuan,
                "VERIFIKASI" if user == self.finance else "DIBAGIKAN",
            )

        self.assertRedirects(self.post_as(self.secretary, "approvecomplete", pk), detail_url)
        disposition.refresh_from_db()
        self.assertEqual(disposition.status_pengajuan, "SELESAI")
        self.assertEqual(disposition.logs.filter(action_log="SELESAI", user_log=self.secretary).count(), 1)
        self.assertEqual(disposition.logs.filter(action_log="SETUJUI_DISPOSISI").count(), 2)
        self.assertEqual(disposition.logs.filter(action_log="TERIMA_DISPOSISI").count(), 2)
        self.assertEqual(disposition.logs.filter(action_log="AKTIVITAS_PENERIMA").count(), 2)
        self.assertTrue(ActivityLog.objects.filter(action="COMPLETION_APPROVED", target_id=str(pk)).exists())
        self.client.force_login(self.secretary)
        self.assertContains(self.client.get(detail_url), "Batalkan Selesai")
