from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import ActivityLog
from disposisi.models import Disposisi, DisposisiRecipient


@override_settings(
    ALLOWED_HOSTS=[
        "testserver",
        "pwujatim.site",
        "www.pwujatim.site",
        "archive.pwujatim.site",
        "localhost",
        "archive.localhost",
    ],
    LANDING_HOSTS=frozenset({"pwujatim.site", "www.pwujatim.site", "localhost"}),
    ARCHIVE_BASE_URL="https://archive.pwujatim.site",
    KOPERASI_BASE_URL="https://koperasi.pwujatim.site",
)
class HostRoutingTests(TestCase):
    def test_public_domain_shows_system_chooser_without_login(self):
        response = self.client.get("/", HTTP_HOST="pwujatim.site")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sistem Arsip")
        self.assertContains(response, "Sistem Koperasi")
        self.assertContains(response, "https://archive.pwujatim.site")
        self.assertContains(response, "https://koperasi.pwujatim.site")
        self.assertNotContains(response, "Masuk ke akun Anda")

    def test_public_domain_does_not_expose_archive_routes(self):
        response = self.client.get(
            reverse("accounts:login"),
            HTTP_HOST="pwujatim.site",
        )

        self.assertRedirects(
            response,
            "/",
            fetch_redirect_response=False,
        )

    def test_archive_domain_still_requires_login(self):
        response = self.client.get(
            reverse("homepage:dashboard"),
            HTTP_HOST="archive.pwujatim.site",
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_localhost_shows_local_system_chooser(self):
        response = self.client.get("/", HTTP_HOST="localhost:8000")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "http://archive.localhost:8000")
        self.assertContains(response, "http://koperasi.localhost:8000")

    def test_archive_localhost_still_requires_login(self):
        response = self.client.get("/", HTTP_HOST="archive.localhost:8000")

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_authenticated_archive_domain_shows_dashboard(self):
        user = get_user_model().objects.create_user(
            username="archive-host-user",
            password="test-password",
            role="kadiv_keuangan",
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("homepage:dashboard"),
            HTTP_HOST="archive.pwujatim.site",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Akses Cepat")


@override_settings(ALLOWED_HOSTS=["testserver"])
class HomepageAuthenticationTests(TestCase):
    def test_feature_pages_require_login(self):
        for name in ("notadinas", "suratkeluar", "inbox", "monitor", "divisi", "notif"):
            with self.subTest(name=name):
                response = self.client.get(reverse(f"homepage:{name}"))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response.url)


@override_settings(ALLOWED_HOSTS=["testserver"])
class DivisionUserListTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.secretary = user_model.objects.create_user(
            username="sekretaris_test",
            password="test-password",
            first_name="Siti",
            last_name="Sekretaris",
            email="siti.sekretaris@pwujatim.site",
            role="sekretaris",
        )
        self.finance_head = user_model.objects.create_user(
            username="kadiv_keuangan_test",
            password="test-password",
            role="kadiv_keuangan",
            is_active=False,
        )
        self.spi_head = user_model.objects.create_user(
            username="kadiv_spi_test",
            password="test-password",
            role="kadiv_spi",
        )
        for username, role in (
            ("dirut", "direktur_utama"),
            ("it_pwu", "admin"),
            ("akuntan1", "akuntan"),
            ("akuntan2", "akuntan"),
        ):
            user, _created = user_model.objects.get_or_create(
                username=username,
                defaults={"role": role},
            )
            user.role = role
            user.set_password("test-password")
            user.save(update_fields=["role", "password"])
        self.wirajatim_user, _ = user_model.objects.update_or_create(
            username="wirajatim_kso",
            defaults={
                "role": "wirajatim_kso",
                "first_name": "Wirajatim",
                "last_name": "KSO",
                "is_active": True,
            },
        )

    def test_division_page_lists_all_users_and_their_roles(self):
        self.client.force_login(self.secretary)

        response = self.client.get(reverse("homepage:divisi"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sekretaris_test")
        self.assertContains(response, "Siti Sekretaris")
        self.assertContains(response, "Email")
        self.assertContains(response, "siti.sekretaris@pwujatim.site")
        self.assertContains(response, "Sekretaris")
        self.assertContains(response, "kadiv_keuangan_test")
        self.assertContains(response, "Kepala Divisi Keuangan")
        self.assertContains(response, "Kepala SPI")
        self.assertNotContains(response, "Kepala Divisi SPI")
        self.assertContains(response, "Nonaktif")
        self.assertContains(response, ">wirajatim_kso<")
        self.assertContains(response, "Wirajatim KSO", count=2)
        for hidden_username in ("dirut", "it_pwu", "akuntan1", "akuntan2"):
            with self.subTest(hidden_username=hidden_username):
                self.assertNotContains(response, f">{hidden_username}<")
        visible_users = get_user_model().objects.exclude(
            username__in={"dirut", "it_pwu", "akuntan1", "akuntan2"},
        ).count()
        self.assertEqual(response.context["users"].count(), visible_users)
        self.assertEqual(response.context["directory_total"], visible_users)
        self.assertContains(
            response,
            f"Total pengguna: {visible_users}",
        )

    def test_wirajatim_kso_login_role_and_password_are_created(self):
        user = get_user_model().objects.get(username="wirajatim_kso")

        self.assertEqual(user.role, "wirajatim_kso")
        self.assertEqual(user.get_role_display(), "Wirajatim KSO")
        self.assertTrue(user.check_password("wirajatim_kso"))

    def test_non_editor_cannot_list_user_directory(self):
        viewer = get_user_model().objects.create_user(
            username="viewer_test",
            password="test-password",
            role="kadiv_risiko",
        )
        self.client.force_login(viewer)

        response = self.client.get(reverse("homepage:divisi"))

        self.assertEqual(response.status_code, 403)

    def test_dashboard_uses_surat_masuk_label(self):
        self.client.force_login(self.secretary)

        response = self.client.get(reverse("homepage:dashboard"))

        self.assertContains(response, "Surat Masuk")

    def test_secretary_can_open_all_archive_pages_except_activity_log(self):
        self.client.force_login(self.secretary)

        allowed_pages = (
            reverse("homepage:dashboard"),
            reverse("disposisi:disposisi"),
            reverse("homepage:notadinas"),
            reverse("homepage:suratkeluar"),
            reverse("homepage:inbox"),
            reverse("homepage:monitor"),
            reverse("homepage:divisi"),
            reverse("homepage:report"),
            reverse("pengaturan:main"),
        )
        for url in allowed_pages:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

        dashboard = self.client.get(reverse("homepage:dashboard"))
        self.assertNotContains(dashboard, "Activity Log")
        self.assertEqual(
            self.client.get(reverse("homepage:activity_log")).status_code,
            403,
        )

    def test_non_secretary_cannot_open_archive_modules(self):
        viewer = get_user_model().objects.create_user(
            username="archive-viewer",
            password="test-password",
            role="kadiv_keuangan",
        )
        self.client.force_login(viewer)

        for url in (
            reverse("disposisi:disposisi"),
            reverse("homepage:notadinas"),
            reverse("homepage:suratkeluar"),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

        dashboard = self.client.get(reverse("homepage:dashboard"))
        self.assertNotContains(dashboard, "Surat Masuk")
        self.assertNotContains(dashboard, "Nota Dinas")
        self.assertNotContains(dashboard, "Surat Keluar")
        self.assertContains(dashboard, "Inbox")
        self.assertContains(dashboard, "Monitor")

    def test_spi_can_open_archive_modules_as_read_only_monitor(self):
        spi = get_user_model().objects.create_user(
            username="spi-monitor",
            password="test-password",
            role="kadiv_spi",
        )
        self.client.force_login(spi)

        for url in (
            reverse("disposisi:disposisi"),
            reverse("homepage:notadinas"),
            reverse("homepage:suratkeluar"),
            reverse("homepage:monitor"),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

        dashboard = self.client.get(reverse("homepage:dashboard"))
        self.assertContains(dashboard, "Surat Masuk")
        self.assertContains(dashboard, "Nota Dinas")
        self.assertContains(dashboard, "Surat Keluar")
        self.assertNotContains(dashboard, "Divisi")
        self.assertEqual(
            self.client.get(reverse("homepage:divisi")).status_code,
            403,
        )


@override_settings(ALLOWED_HOSTS=["testserver"])
class DocumentQueueTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.secretary = user_model.objects.create_user(
            username="queue-secretary",
            password="test-password",
            role="sekretaris",
        )
        self.finance_head = user_model.objects.create_user(
            username="queue-finance",
            password="test-password",
            role="kadiv_keuangan",
        )
        self.pending = self.create_document("PENDING-001", "DIBAGIKAN")
        DisposisiRecipient.objects.create(
            disposisi=self.pending,
            role="kadiv_keuangan",
        )
        self.completed = self.create_document("DONE-001", "SELESAI")
        DisposisiRecipient.objects.create(
            disposisi=self.completed,
            role="kadiv_keuangan",
            agreed_at=timezone.now(),
        )
        self.unrelated = self.create_document("OTHER-001", "DIBAGIKAN")

    @staticmethod
    def create_document(number, status):
        return Disposisi.objects.create(
            tanggal_surat_diterima=date(2026, 7, 27),
            tanggal_surat=date(2026, 7, 27),
            nomor_surat=number,
            pengirim="Pengirim Uji",
            lampiran="-",
            tujuan="DIR",
            tembusan="-",
            perihal=f"Perihal {number}",
            tujuan_disposisi="kadiv_keuangan",
            tipe_disposisi="ONLINE",
            status_pengajuan=status,
            dokumen_surat_masuk=f"tests/{number}.pdf",
        )

    def test_monitor_lists_all_documents_related_to_recipient(self):
        self.client.force_login(self.finance_head)

        response = self.client.get(reverse("homepage:monitor"))

        self.assertContains(response, "PENDING-001")
        self.assertContains(response, "DONE-001")
        self.assertNotContains(response, "OTHER-001")

    def test_inbox_only_lists_documents_needing_action(self):
        self.client.force_login(self.finance_head)

        response = self.client.get(reverse("homepage:inbox"))

        self.assertContains(response, "PENDING-001")
        self.assertNotContains(response, "DONE-001")
        self.assertNotContains(response, "OTHER-001")

    def test_secretary_monitor_lists_all_documents(self):
        self.client.force_login(self.secretary)

        response = self.client.get(reverse("homepage:monitor"))

        self.assertContains(response, "PENDING-001")
        self.assertContains(response, "DONE-001")
        self.assertContains(response, "OTHER-001")


@override_settings(ALLOWED_HOSTS=["testserver"])
class ActivityLogAccessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.it_user = user_model.objects.get(username="it_pwu")
        self.it_user.role = "admin"
        self.it_user.set_password("test-password")
        self.it_user.save(update_fields=["role", "password"])
        self.other_admin = user_model.objects.create_user(
            username="audit-admin",
            password="test-password",
            role="admin",
            is_superuser=True,
            is_staff=True,
        )
        self.regular_user = user_model.objects.create_user(
            username="audit-viewer",
            password="test-password",
            role="kadiv_keuangan",
        )
        ActivityLog.objects.create(
            actor=self.regular_user,
            actor_username=self.regular_user.username,
            category="DISPOSISI",
            action="DIEDIT",
            description="Disposition updated.",
            target_type="disposisi.Disposisi",
            target_id="12",
            target_label="12/VII/2026",
        )

    def test_activity_log_is_visible_to_it_pwu(self):
        self.client.force_login(self.it_user)

        response = self.client.get(reverse("homepage:activity_log"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Activity Log")
        self.assertContains(response, "audit-viewer")
        self.assertContains(response, "DIEDIT")
        self.assertContains(response, "12/VII/2026")

    def test_activity_log_rejects_non_admin(self):
        self.client.force_login(self.regular_user)

        response = self.client.get(reverse("homepage:activity_log"))

        self.assertEqual(response.status_code, 403)

    def test_activity_log_rejects_other_admin_and_superuser(self):
        self.client.force_login(self.other_admin)

        response = self.client.get(reverse("homepage:activity_log"))

        self.assertEqual(response.status_code, 403)

    def test_activity_log_filters_by_category_and_result(self):
        ActivityLog.objects.create(
            actor_username="unknown-user",
            category="AUTH",
            action="LOGIN_FAILED",
            description="Login attempt failed.",
            success=False,
        )
        self.client.force_login(self.it_user)

        response = self.client.get(
            reverse("homepage:activity_log"),
            {"category": "AUTH", "result": "failed"},
        )

        self.assertContains(response, "LOGIN_FAILED")
        self.assertNotContains(response, "12/VII/2026")
