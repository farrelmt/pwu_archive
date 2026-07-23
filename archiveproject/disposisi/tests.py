from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import SystemUser
from .models import Disposisi


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.InMemoryStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    },
)
class DisposisiSecurityTests(TestCase):
    def setUp(self):
        self.editor = SystemUser.objects.create_user(
            username="editor",
            password="password-for-tests",
            role="sekretaris",
        )
        self.admin = SystemUser.objects.create_user(
            username="admin-editor",
            password="password-for-tests",
            role="admin",
        )
        self.viewer = SystemUser.objects.create_user(
            username="viewer",
            password="password-for-tests",
            role="kadiv",
        )
        self.director = SystemUser.objects.create_user(
            username="director",
            password="password-for-tests",
            role="direktur_umum",
        )
        self.main_director = SystemUser.objects.create_user(
            username="main-director",
            password="password-for-tests",
            role="direktur_utama",
        )
        self.accounting_head = SystemUser.objects.create_user(
            username="accounting-head",
            password="password-for-tests",
            role="kadiv_akuntansi",
        )
        self.finance_head = SystemUser.objects.create_user(
            username="finance-head",
            password="password-for-tests",
            role="kadiv_keuangan",
        )
        self.risk_head = SystemUser.objects.create_user(
            username="risk-head",
            password="password-for-tests",
            role="kadiv_risiko",
        )
        self.disposisi = self.make_disposisi()

    def make_disposisi(self):
        return Disposisi.objects.create(
            tanggal_surat_diterima=date(2026, 7, 17),
            tanggal_surat=date(2026, 7, 16),
            nomor_surat="001/TEST",
            pengirim="Pengirim",
            lampiran="1",
            tujuan="DIR",
            tembusan="-",
            perihal="Test",
            tujuan_disposisi="Direktur",
            dokumen_surat_masuk=SimpleUploadedFile(
                "surat.pdf", b"%PDF-1.4 test", content_type="application/pdf"
            ),
        )

    def test_delete_rejects_get(self):
        self.client.force_login(self.editor)

        response = self.client.get(
            reverse("disposisi:hapusdisposisi", args=[self.disposisi.pk])
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Disposisi.objects.filter(pk=self.disposisi.pk).exists())

    def test_non_editor_cannot_delete(self):
        self.client.force_login(self.viewer)

        response = self.client.post(
            reverse("disposisi:hapusdisposisi", args=[self.disposisi.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Disposisi.objects.filter(pk=self.disposisi.pk).exists())

    def test_editor_can_delete_with_post(self):
        self.client.force_login(self.editor)

        response = self.client.post(
            reverse("disposisi:hapusdisposisi", args=[self.disposisi.pk])
        )

        self.assertRedirects(response, reverse("disposisi:disposisi"))
        self.assertFalse(Disposisi.objects.filter(pk=self.disposisi.pk).exists())

    def test_upload_rejects_disallowed_file(self):
        self.client.force_login(self.editor)
        uploaded = SimpleUploadedFile(
            "payload.exe", b"not an image", content_type="application/octet-stream"
        )

        response = self.client.post(
            reverse("disposisi:uploaddisposisi", args=[self.disposisi.pk]),
            {
                "metode": "OFFLINE",
                "dokumen_disposisi": uploaded,
                "recipients": ["kadiv_akuntansi"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Format file tidak diizinkan")
        self.disposisi.refresh_from_db()
        self.assertFalse(self.disposisi.dokumen_disposisi)

    def test_non_editor_cannot_upload(self):
        self.client.force_login(self.viewer)
        uploaded = SimpleUploadedFile(
            "disposisi.pdf", b"%PDF-1.4 test", content_type="application/pdf"
        )

        response = self.client.post(
            reverse("disposisi:uploaddisposisi", args=[self.disposisi.pk]),
            {"metode": "OFFLINE", "dokumen_disposisi": uploaded},
        )

        self.assertEqual(response.status_code, 403)

    def test_editor_detail_renders_tidy_created_action_toolbar(self):
        self.client.force_login(self.editor)

        response = self.client.get(
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk])
        )

        for label in (
            "Kembali",
            "History",
            "Edit",
            "Dokumen Surat",
            "Preview",
            "Lanjutkan",
            "Metode Disposisi",
            "Belum Dipilih",
        ):
            with self.subTest(label=label):
                self.assertContains(response, label)
        self.assertContains(response, "fixed bottom-0")

    def test_detail_shows_offline_processing_method(self):
        self.disposisi.tipe_disposisi = "OFFLINE"
        self.disposisi.save(update_fields=["tipe_disposisi"])
        self.client.force_login(self.editor)

        response = self.client.get(
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk])
        )

        self.assertContains(response, "Metode Disposisi")
        self.assertContains(response, "Offline")

    def submit_online(self, roles=None):
        self.client.force_login(self.editor)
        return self.client.post(
            reverse("disposisi:uploaddisposisi", args=[self.disposisi.pk]),
            {
                "metode": "ONLINE",
                "recipients": roles or ["kadiv_akuntansi"],
            },
        )

    def upload_offline(self, roles=None, user=None):
        self.client.force_login(user or self.editor)
        uploaded = SimpleUploadedFile(
            "disposisi.pdf",
            b"%PDF-1.4 offline test",
            content_type="application/pdf",
        )
        return self.client.post(
            reverse("disposisi:uploaddisposisi", args=[self.disposisi.pk]),
            {
                "metode": "OFFLINE",
                "dokumen_disposisi": uploaded,
                "recipients": roles or ["kadiv_akuntansi"],
            },
        )

    def test_method_page_requires_recipient_selection(self):
        self.client.force_login(self.editor)

        page_response = self.client.get(
            reverse("disposisi:uploaddisposisi", args=[self.disposisi.pk])
        )
        submit_response = self.client.post(
            reverse("disposisi:uploaddisposisi", args=[self.disposisi.pk]),
            {"metode": "ONLINE"},
        )

        self.assertContains(page_response, "Bagikan Kepada")
        self.assertContains(page_response, "Kepala Divisi Keuangan")
        self.assertContains(submit_response, "Pilih minimal satu tujuan disposisi")
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "DIBUAT")

    def test_offline_upload_with_recipients_completes_progress(self):
        response = self.upload_offline(
            ["kadiv_akuntansi", "kadiv_keuangan"]
        )

        self.assertRedirects(
            response,
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk]),
        )
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.tipe_disposisi, "OFFLINE")
        self.assertEqual(self.disposisi.status_pengajuan, "SELESAI")
        self.assertSetEqual(
            set(self.disposisi.shared_recipients.values_list("role", flat=True)),
            {"kadiv_akuntansi", "kadiv_keuangan"},
        )

        detail_response = self.client.get(
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk])
        )
        preview_response = self.client.get(
            reverse("disposisi:previewdisposisi", args=[self.disposisi.pk])
        )
        self.assertNotContains(detail_response, 'id="openShareModal"')
        self.assertContains(detail_response, "Kepala Divisi Akuntansi")
        self.assertContains(detail_response, "Kepala Divisi Keuangan")
        self.assertContains(preview_response, "✓", count=2)
        self.assertContains(
            preview_response,
            '<div class="checkbox">✓</div><span class="checkbox-text">Kepala Divisi Keuangan</span>',
            html=True,
        )
        self.assertTrue(
            self.disposisi.logs.filter(action_log="BAGI_DISPOSISI").exists()
        )
        self.assertTrue(self.disposisi.logs.filter(action_log="SELESAI").exists())

    def test_admin_can_select_recipient_while_uploading_offline(self):
        response = self.upload_offline(["kadiv_aset"], user=self.admin)

        self.assertRedirects(
            response,
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk]),
        )
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "SELESAI")
        self.assertTrue(
            self.disposisi.shared_recipients.filter(role="kadiv_aset").exists()
        )

    def approve_online(self, roles=None):
        self.submit_online(roles)
        self.client.force_login(self.director)
        return self.client.post(
            reverse("disposisi:isionline", args=[self.disposisi.pk]),
            {"isi_disposisi": "<p>Mohon ditindaklanjuti.</p>"},
        )

    def share_online(self, roles):
        return self.approve_online(roles)

    def test_editor_can_submit_online_request(self):
        self.disposisi.isi_disposisi = "<p>Isi lama.</p>"
        self.disposisi.save(update_fields=["isi_disposisi"])
        response = self.submit_online()

        self.assertRedirects(
            response,
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk]),
        )
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.tipe_disposisi, "ONLINE")
        self.assertEqual(self.disposisi.status_pengajuan, "DIAJUKAN")
        self.assertEqual(self.disposisi.isi_disposisi, "")
        self.assertTrue(
            self.disposisi.logs.filter(action_log="AJUKAN_DISPOSISI").exists()
        )

        detail_response = self.client.get(
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk])
        )
        self.assertContains(detail_response, "Metode Disposisi")
        self.assertContains(detail_response, "Online")

    def test_pending_disposition_for_director_only_reaches_director(self):
        self.submit_online()
        isi_url = reverse("disposisi:isionline", args=[self.disposisi.pk])
        decision_url = reverse(
            "disposisi:decisiononline",
            args=[self.disposisi.pk],
        )

        self.client.force_login(self.main_director)
        wrong_monitor = self.client.get(reverse("homepage:monitor"))
        wrong_editor = self.client.get(isi_url)
        wrong_decision = self.client.post(decision_url, {"keputusan": "TOLAK"})

        self.assertNotContains(wrong_monitor, self.disposisi.nomor_surat)
        self.assertEqual(wrong_editor.status_code, 403)
        self.assertEqual(wrong_decision.status_code, 403)

        self.client.force_login(self.director)
        correct_monitor = self.client.get(reverse("homepage:monitor"))
        dashboard_response = self.client.get(reverse("homepage:dashboard"))
        self.assertContains(correct_monitor, self.disposisi.nomor_surat)
        self.assertContains(dashboard_response, 'id="notificationBadge"')
        self.assertContains(dashboard_response, "1 tugas perlu diproses")

    def test_pending_disposition_for_main_director_only_reaches_main_director(self):
        self.disposisi.tujuan = "DIRUT"
        self.disposisi.save(update_fields=["tujuan"])
        self.submit_online()

        self.client.force_login(self.director)
        regular_monitor = self.client.get(reverse("homepage:monitor"))
        self.assertNotContains(regular_monitor, self.disposisi.nomor_surat)

        self.client.force_login(self.main_director)
        main_monitor = self.client.get(reverse("homepage:monitor"))
        editor_response = self.client.get(
            reverse("disposisi:isionline", args=[self.disposisi.pk])
        )
        self.assertContains(main_monitor, self.disposisi.nomor_surat)
        self.assertEqual(editor_response.status_code, 200)
        self.assertContains(main_monitor, "Menunggu Direktur")

    def test_editor_can_cancel_pending_online_request(self):
        self.submit_online()
        self.disposisi.isi_disposisi = "<p>Draft yang harus dihapus.</p>"
        self.disposisi.save(update_fields=["isi_disposisi"])

        detail_response = self.client.get(
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk])
        )

        self.assertContains(detail_response, "Menunggu Persetujuan")
        self.assertContains(detail_response, "Batalkan Disposisi Online")
        self.assertContains(
            detail_response,
            reverse("disposisi:cancelonline", args=[self.disposisi.pk]),
        )

        response = self.client.post(
            reverse("disposisi:cancelonline", args=[self.disposisi.pk])
        )

        self.assertRedirects(
            response,
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk]),
        )
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.tipe_disposisi, "BELUM")
        self.assertEqual(self.disposisi.status_pengajuan, "DIBUAT")
        self.assertEqual(self.disposisi.isi_disposisi, "")

    def test_director_sees_pending_request_and_can_approve(self):
        self.submit_online()
        self.client.force_login(self.director)

        monitor_response = self.client.get(reverse("homepage:monitor"))
        detail_response = self.client.get(
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk])
        )
        isi_url = reverse("disposisi:isionline", args=[self.disposisi.pk])
        editor_response = self.client.get(isi_url)

        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "DIAJUKAN")

        send_response = self.client.post(
            isi_url,
            {
                "isi_disposisi": (
                    '<p onclick="alert(1)"><strong>Setujui</strong> pengadaan.</p>'
                    '<svg data-signature-overlay="true" viewBox="0 0 700 330" '
                    'onload="alert(1)"><path d="M 20 40 L 80 90" '
                    'stroke="red" onclick="alert(1)"></path>'
                    '<script>alert("svg-xss")</script></svg>'
                    '<script>alert("xss")</script>'
                )
            },
        )

        self.assertContains(monitor_response, self.disposisi.nomor_surat)
        self.assertContains(monitor_response, "table-fixed")
        self.assertContains(
            monitor_response,
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk]),
        )
        self.assertContains(detail_response, "Isi Disposisi")
        self.assertContains(detail_response, isi_url)
        self.assertNotContains(
            detail_response,
            reverse("disposisi:editdisposisi", args=[self.disposisi.pk]),
        )
        self.assertNotContains(detail_response, "Lanjutkan")
        self.assertContains(editor_response, 'contenteditable="true"')
        self.assertContains(editor_response, "editorToolbar")
        self.assertContains(editor_response, "Gambar langsung pada dokumen")
        self.assertContains(editor_response, "previewDocumentMount")
        self.assertNotContains(editor_response, "signatureModal")
        self.assertContains(editor_response, "width: 210mm")
        self.assertContains(editor_response, "height: 297mm")
        self.assertContains(editor_response, "max-height: 297mm")
        self.assertContains(editor_response, "aspect-ratio: 210 / 297")
        self.assertContains(
            editor_response,
            "const horizontalOffset = (",
        )
        self.assertContains(editor_response, "const verticalOffset =")
        self.assertContains(editor_response, "editor.clientHeight")
        self.assertContains(editor_response, "contentLimitWarning")
        self.assertContains(editor_response, "body > div:first-of-type > div.flex")
        self.assertContains(editor_response, "#isiDisposisiForm")
        self.assertNotContains(editor_response, 'id="drawingCancelRow"')
        self.assertContains(editor_response, "flex-wrap: nowrap")
        self.assertContains(editor_response, 'class="online-document-header"')
        self.assertContains(editor_response, 'class="destination-option"')
        self.assertContains(editor_response, 'class="isi-title"')
        self.assertContains(editor_response, "margin-top: 30px")
        self.assertNotContains(editor_response, 'class="isi-section border-')
        self.assertContains(editor_response, "Preview")
        self.assertContains(editor_response, "Kirim")
        self.assertRedirects(
            send_response,
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk]),
        )
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.tipe_disposisi, "ONLINE")
        self.assertEqual(self.disposisi.status_pengajuan, "DIBAGIKAN")
        self.assertIn("<strong>Setujui</strong>", self.disposisi.isi_disposisi)
        self.assertIn('data-signature-overlay="true"', self.disposisi.isi_disposisi)
        self.assertIn(
            'preserveAspectRatio="xMidYMax meet"',
            self.disposisi.isi_disposisi,
        )
        self.assertIn('stroke="#111827"', self.disposisi.isi_disposisi)
        self.assertNotIn("onclick", self.disposisi.isi_disposisi)
        self.assertNotIn('stroke="red"', self.disposisi.isi_disposisi)
        self.assertNotIn("onload", self.disposisi.isi_disposisi)
        self.assertNotIn("script", self.disposisi.isi_disposisi)
        self.assertTrue(
            self.disposisi.logs.filter(
                action_log="SETUJUI_DISPOSISI", user_log=self.director
            ).exists()
        )

    def test_director_can_reject_pending_request(self):
        self.submit_online()
        self.disposisi.isi_disposisi = "<p>Draft yang ditolak.</p>"
        self.disposisi.save(update_fields=["isi_disposisi"])
        self.client.force_login(self.director)

        self.client.post(
            reverse("disposisi:decisiononline", args=[self.disposisi.pk]),
            {"keputusan": "TOLAK", "alasan": "Data belum lengkap."},
        )

        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.tipe_disposisi, "BELUM")
        self.assertEqual(self.disposisi.status_pengajuan, "DIBUAT")
        self.assertEqual(self.disposisi.isi_disposisi, "")
        rejection = self.disposisi.logs.get(action_log="TOLAK_DISPOSISI")
        self.assertEqual(rejection.keterangan_log, "Data belum lengkap.")

    def test_recipients_are_selected_before_online_approval(self):
        self.submit_online(["kadiv_akuntansi", "kadiv_keuangan"])
        self.client.force_login(self.editor)

        detail_response = self.client.get(
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk])
        )
        self.assertContains(detail_response, "Kepala Divisi Akuntansi")
        self.assertContains(detail_response, "Kepala Divisi Keuangan")
        self.assertContains(detail_response, "Dipilih", count=2)
        self.assertNotContains(detail_response, 'id="openShareModal"')

        preview_response = self.client.get(
            reverse("disposisi:previewdisposisi", args=[self.disposisi.pk])
        )
        self.assertContains(preview_response, "✓", count=2)

        self.client.force_login(self.director)
        response = self.client.post(
            reverse("disposisi:isionline", args=[self.disposisi.pk]),
            {"isi_disposisi": "<p>Mohon ditindaklanjuti.</p>"},
        )

        self.assertRedirects(
            response,
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk]),
        )
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "DIBAGIKAN")
        self.assertSetEqual(
            set(self.disposisi.shared_recipients.values_list("role", flat=True)),
            {"kadiv_akuntansi", "kadiv_keuangan"},
        )
        share_log = self.disposisi.logs.get(action_log="BAGI_DISPOSISI")
        self.assertIn("Kepala Divisi Akuntansi", share_log.keterangan_log)
        self.assertIn("Kepala Divisi Keuangan", share_log.keterangan_log)

        shared_detail = self.client.get(
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk])
        )
        self.assertContains(shared_detail, 'id="sharedRecipientDescription"')
        self.assertContains(shared_detail, "Dibagikan Kepada")
        self.assertContains(shared_detail, "Kepala Divisi Akuntansi")
        self.assertContains(shared_detail, "Kepala Divisi Keuangan")
        self.assertContains(shared_detail, "Belum menyetujui", count=2)
        self.assertContains(shared_detail, "bg-red-100")

    def test_only_selected_roles_see_shared_disposition_in_monitor(self):
        self.share_online(["kadiv_akuntansi", "kadiv_keuangan"])

        for selected_user in (self.accounting_head, self.finance_head):
            with self.subTest(role=selected_user.role):
                self.client.force_login(selected_user)
                response = self.client.get(reverse("homepage:monitor"))
                self.assertContains(response, self.disposisi.nomor_surat)
                self.assertContains(response, "Disposisi Dibagikan")
                self.assertContains(response, 'id="notificationBadge"')

        self.client.force_login(self.risk_head)
        risk_response = self.client.get(reverse("homepage:monitor"))
        self.assertNotContains(risk_response, self.disposisi.nomor_surat)
        self.assertNotContains(risk_response, 'id="notificationBadge"')

        self.client.force_login(self.editor)
        secretary_response = self.client.get(reverse("homepage:monitor"))
        self.assertNotContains(secretary_response, self.disposisi.nomor_surat)

    def test_recipient_cannot_replace_preselected_online_recipients(self):
        self.approve_online()
        self.client.force_login(self.accounting_head)

        response = self.client.post(
            reverse("disposisi:shareonline", args=[self.disposisi.pk]),
            {"recipients": ["kadiv_akuntansi"]},
        )

        self.assertEqual(response.status_code, 403)
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "DIBAGIKAN")
        self.assertSetEqual(
            set(self.disposisi.shared_recipients.values_list("role", flat=True)),
            {"kadiv_akuntansi"},
        )

    def test_online_method_requires_at_least_one_recipient(self):
        self.client.force_login(self.editor)

        response = self.client.post(
            reverse("disposisi:uploaddisposisi", args=[self.disposisi.pk]),
            {"metode": "ONLINE"},
            follow=True,
        )

        self.assertContains(response, "Pilih minimal satu tujuan disposisi")
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "DIBUAT")

    def test_recipient_can_read_shared_online_content(self):
        self.share_online(["kadiv_akuntansi"])
        self.client.force_login(self.accounting_head)

        response = self.client.get(
            reverse("disposisi:isionline", args=[self.disposisi.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mohon ditindaklanjuti.")
        self.assertNotContains(response, 'role="textbox"')
        self.assertNotContains(response, ">Kirim<")

    def test_disposition_finishes_only_after_all_recipients_agree(self):
        self.share_online(["kadiv_akuntansi", "kadiv_keuangan"])
        self.client.force_login(self.accounting_head)
        complete_url = reverse(
            "disposisi:completeonline",
            args=[self.disposisi.pk],
        )

        detail_response = self.client.get(
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk])
        )
        self.assertContains(detail_response, complete_url)
        self.assertContains(detail_response, "Setujui")

        response = self.client.post(complete_url)

        self.assertRedirects(
            response,
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk]),
        )
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "DIBAGIKAN")
        accounting_recipient = self.disposisi.shared_recipients.get(
            role="kadiv_akuntansi"
        )
        finance_recipient = self.disposisi.shared_recipients.get(
            role="kadiv_keuangan"
        )
        self.assertIsNotNone(accounting_recipient.agreed_at)
        self.assertIsNone(finance_recipient.agreed_at)
        acceptance_log = self.disposisi.logs.get(action_log="TERIMA_DISPOSISI")
        self.assertEqual(acceptance_log.user_log, self.accounting_head)
        self.assertFalse(self.disposisi.logs.filter(action_log="SELESAI").exists())

        monitor_response = self.client.get(reverse("homepage:monitor"))
        self.assertNotContains(monitor_response, self.disposisi.nomor_surat)

        partially_accepted_detail = self.client.get(
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk])
        )
        self.assertContains(partially_accepted_detail, "Sudah menyetujui")
        self.assertContains(partially_accepted_detail, "Belum menyetujui")
        self.assertContains(partially_accepted_detail, "bg-green-100")
        self.assertContains(partially_accepted_detail, "bg-red-100")
        self.assertNotContains(partially_accepted_detail, complete_url)

        self.client.force_login(self.finance_head)
        finance_monitor = self.client.get(reverse("homepage:monitor"))
        self.assertContains(finance_monitor, self.disposisi.nomor_surat)

        finance_detail = self.client.get(
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk])
        )
        self.assertContains(finance_detail, complete_url)
        self.assertContains(finance_detail, "Setujui")

        final_response = self.client.post(complete_url)
        self.assertRedirects(
            final_response,
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk]),
        )
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "SELESAI")
        self.assertEqual(
            self.disposisi.shared_recipients.filter(
                agreed_at__isnull=False
            ).count(),
            2,
        )
        completion_log = self.disposisi.logs.get(action_log="SELESAI")
        self.assertEqual(completion_log.user_log, self.finance_head)
        self.assertIn("Seluruh penerima", completion_log.keterangan_log)

        completed_monitor = self.client.get(reverse("homepage:monitor"))
        self.assertNotContains(completed_monitor, self.disposisi.nomor_surat)

        completed_detail = self.client.get(
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk])
        )
        self.assertContains(completed_detail, "Selesai")
        self.assertContains(completed_detail, 'id="sharedRecipientDescription"')
        self.assertContains(completed_detail, "Kepala Divisi Akuntansi")
        self.assertContains(completed_detail, "Kepala Divisi Keuangan")
        self.assertContains(completed_detail, "Sudah menyetujui", count=2)
        self.assertNotContains(completed_detail, "Belum menyetujui")
        self.assertNotContains(completed_detail, complete_url)

    def test_unselected_role_cannot_complete_shared_disposition(self):
        self.share_online(["kadiv_akuntansi"])
        self.client.force_login(self.finance_head)
        complete_url = reverse(
            "disposisi:completeonline",
            args=[self.disposisi.pk],
        )

        get_response = self.client.get(complete_url)
        post_response = self.client.post(complete_url)

        self.assertEqual(get_response.status_code, 405)
        self.assertEqual(post_response.status_code, 403)
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "DIBAGIKAN")
        self.assertFalse(
            self.disposisi.logs.filter(action_log="TERIMA_DISPOSISI").exists()
        )
        self.assertFalse(self.disposisi.logs.filter(action_log="SELESAI").exists())

    def test_editor_can_open_approved_online_edit_without_file(self):
        self.submit_online()
        self.client.force_login(self.director)
        self.client.post(
            reverse("disposisi:isionline", args=[self.disposisi.pk]),
            {"isi_disposisi": "<p>Disetujui.</p>"},
        )
        self.client.force_login(self.editor)

        response = self.client.get(
            reverse("disposisi:editdisposisi", args=[self.disposisi.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Belum ada file")
        self.assertNotContains(response, "data-dokumendisposisi=\" /media/")

        update_response = self.client.post(
            reverse("disposisi:editdisposisi", args=[self.disposisi.pk]),
            {
                "tanggal_surat_diterima": "2026-07-17",
                "tanggal_surat": "2026-07-16",
                "nomor_surat": "001/TEST",
                "pengirim": "Pengirim",
                "lampiran": "1",
                "tujuan": "DIR",
                "tembusan": "-",
                "perihal": "Test diperbarui",
            },
        )

        self.assertRedirects(
            update_response,
            reverse("disposisi:detaildisposisi", args=[self.disposisi.pk]),
        )
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "DIBUAT")
        self.assertEqual(self.disposisi.isi_disposisi, "")

    def test_non_director_cannot_decide_online_request(self):
        self.submit_online()

        response = self.client.post(
            reverse("disposisi:decisiononline", args=[self.disposisi.pk]),
            {"keputusan": "SETUJUI"},
        )

        self.assertEqual(response.status_code, 403)
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "DIAJUKAN")

        editor_response = self.client.get(
            reverse("disposisi:isionline", args=[self.disposisi.pk])
        )
        self.assertEqual(editor_response.status_code, 403)

    def test_empty_online_content_does_not_approve(self):
        self.submit_online()
        self.client.force_login(self.director)

        response = self.client.post(
            reverse("disposisi:isionline", args=[self.disposisi.pk]),
            {"isi_disposisi": "<p><br></p>"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Isi disposisi wajib diisi")
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "DIAJUKAN")

    def test_online_content_over_a4_limit_does_not_approve(self):
        self.submit_online()
        self.client.force_login(self.director)

        response = self.client.post(
            reverse("disposisi:isionline", args=[self.disposisi.pk]),
            {"isi_disposisi": f"<p>{'A' * 2401}</p>"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "melebihi batas satu halaman A4")
        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "DIAJUKAN")
        self.assertEqual(self.disposisi.isi_disposisi, "")

    def test_approved_online_content_is_read_only(self):
        self.submit_online()
        self.client.force_login(self.director)
        isi_url = reverse("disposisi:isionline", args=[self.disposisi.pk])
        self.client.post(isi_url, {"isi_disposisi": "<p>Mohon ditindaklanjuti.</p>"})
        self.client.force_login(self.editor)

        response = self.client.get(isi_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mohon ditindaklanjuti.")
        self.assertNotContains(response, 'role="textbox"')
        self.assertNotContains(response, ">Kirim<")

    def test_processed_request_cannot_be_decided_again(self):
        self.submit_online()
        self.client.force_login(self.director)
        decision_url = reverse(
            "disposisi:decisiononline", args=[self.disposisi.pk]
        )
        self.client.post(
            reverse("disposisi:isionline", args=[self.disposisi.pk]),
            {"isi_disposisi": "<p>Disetujui.</p>"},
        )

        self.client.post(decision_url, {"keputusan": "TOLAK"})

        self.disposisi.refresh_from_db()
        self.assertEqual(self.disposisi.status_pengajuan, "DIBAGIKAN")
        self.assertFalse(
            self.disposisi.logs.filter(action_log="TOLAK_DISPOSISI").exists()
        )
