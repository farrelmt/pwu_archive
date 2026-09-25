from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import ActivityLog
from disposisi.models import Disposisi, DisposisiRecipient
from inventory.models import InventoryAccess
from koperasi.models import KoperasiAccess
from risk_management.models import RiskAccess, RiskDivision


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
    ARCHIVE_HOSTS=frozenset({"archive.pwujatim.site", "archive.localhost"}),
    PORTAL_BASE_URL="https://pwujatim.site",
    ARCHIVE_BASE_URL="https://archive.pwujatim.site",
    KOPERASI_BASE_URL="https://koperasi.pwujatim.site",
)
class HostRoutingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="portal-user",
            password="test-password",
            role="employee",
        )
        InventoryAccess.objects.create(
            user=self.user,
            role="participant",
            is_active=True,
        )

    def test_public_domain_requires_login_before_system_chooser(self):
        response = self.client.get("/", HTTP_HOST="pwujatim.site")

        self.assertRedirects(response, "/accounts/login/", fetch_redirect_response=False)

    def test_authenticated_public_domain_shows_system_chooser(self):
        self.client.force_login(self.user)
        response = self.client.get("/", HTTP_HOST="pwujatim.site")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, ">Sistem Arsip<")
        self.assertNotContains(response, ">Sistem Koperasi<")
        self.assertNotContains(response, ">Manajemen Risiko<")
        self.assertContains(response, ">Sistem Inventaris<")
        self.assertNotContains(response, "/accounts/system/archive/")
        self.assertNotContains(response, "/accounts/system/koperasi/")
        self.assertContains(response, "Pengaturan")
        self.assertContains(response, self.user.username)
        self.assertContains(response, "Keluar")
        self.assertNotContains(response, "Kelola Member")
        self.assertNotContains(response, "Masuk ke akun Anda")

    def test_public_domain_exposes_central_login(self):
        response = self.client.get(
            reverse("accounts:login"),
            HTTP_HOST="pwujatim.site",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Portal Sistem Informasi PWU Jatim")

    def test_archive_domain_still_requires_login(self):
        response = self.client.get(
            reverse("homepage:dashboard"),
            HTTP_HOST="archive.pwujatim.site",
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("https://pwujatim.site/accounts/login/"))
        self.assertIn("archive.pwujatim.site", response.url)

    def test_localhost_shows_local_system_chooser(self):
        self.client.force_login(self.user)
        response = self.client.get("/", HTTP_HOST="localhost:8000")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "/accounts/system/archive/")
        self.assertNotContains(response, "/accounts/system/koperasi/")
        self.assertContains(response, "/accounts/system/inventory/")

    def test_local_system_launch_uses_signed_subdomain_handoff(self):
        self.user.role = "kadiv_keuangan"
        self.user.save(update_fields=["role"])
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("accounts:system_launch", args=["archive"]),
            HTTP_HOST="localhost:8000",
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.url.startswith(
                "http://archive.localhost:8000/accounts/handoff/?token="
            )
        )

        handoff_path = response.url.split("archive.localhost:8000", 1)[1]
        response = self.client.get(handoff_path, HTTP_HOST="archive.localhost:8000")
        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_system_launch_denies_user_without_system_role(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("accounts:system_launch", args=["archive"]),
            HTTP_HOST="localhost:8000",
        )

        self.assertEqual(response.status_code, 403)

    def test_portal_shows_koperasi_only_after_role_is_assigned(self):
        KoperasiAccess.objects.create(
            user=self.user,
            company=None,
            role="auditor",
            is_active=True,
        )
        self.client.force_login(self.user)

        response = self.client.get("/", HTTP_HOST="pwujatim.site")

        self.assertContains(response, ">Sistem Koperasi<")
        self.assertContains(response, "/accounts/system/koperasi/")

    def test_authenticated_archive_domain_denies_user_without_archive_role(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("homepage:dashboard"),
            HTTP_HOST="archive.pwujatim.site",
        )

        self.assertEqual(response.status_code, 403)

    def test_archive_localhost_still_requires_login(self):
        response = self.client.get("/", HTTP_HOST="archive.localhost:8000")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("http://localhost:8000/accounts/login/"))
        self.assertIn("archive.localhost", response.url)

    def test_authenticated_archive_domain_shows_dashboard(self):
        self.user.role = "kadiv_keuangan"
        self.user.save(update_fields=["role"])
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("homepage:dashboard"),
            HTTP_HOST="archive.pwujatim.site",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Akses Cepat")


@override_settings(
    ALLOWED_HOSTS=["testserver", "pwujatim.site"],
    LANDING_HOSTS=frozenset({"pwujatim.site"}),
)
class MemberManagementTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            username="farrel_mt",
            password="admin-password",
            role="employee",
        )
        self.viewer = user_model.objects.create_user(
            username="ordinary_user",
            password="viewer-password",
            role="employee",
        )
        self.division = RiskDivision.objects.get(code="AKT")

    def test_named_member_admin_can_open_member_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("homepage:member_list"),
            HTTP_HOST="pwujatim.site",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Member & Akses")
        self.assertContains(response, "ordinary_user")

    def test_named_member_admin_sees_member_link_in_portal_navbar(self):
        self.client.force_login(self.admin)
        response = self.client.get("/", HTTP_HOST="pwujatim.site")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kelola Member")

    def test_ordinary_user_cannot_open_member_page(self):
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse("homepage:member_list"),
            HTTP_HOST="pwujatim.site",
        )

        self.assertEqual(response.status_code, 403)

    def test_member_admin_can_create_user_and_all_system_access(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("homepage:member_create"),
            {
                "username": "new_member",
                "first_name": "Member",
                "last_name": "Baru",
                "email": "member@pwujatim.site",
                "phone": "08123456789",
                "password": "secure-password",
                "password_confirm": "secure-password",
                "role": "kadiv_akuntansi",
                "koperasi_roles": ["treasurer", "supervisor"],
                "risk_roles": ["risk_officer", "division_head"],
                "risk_division": self.division.pk,
                "inventory_role": "officer",
                "is_active": "on",
            },
            HTTP_HOST="pwujatim.site",
        )

        self.assertRedirects(
            response,
            reverse("homepage:member_list"),
            fetch_redirect_response=False,
        )
        user = get_user_model().objects.get(username="new_member")
        self.assertTrue(user.check_password("secure-password"))
        self.assertEqual(user.role, "kadiv_akuntansi")
        self.assertEqual(
            set(KoperasiAccess.objects.filter(user=user, company=None).values_list("role", flat=True)),
            {"treasurer", "supervisor"},
        )
        self.assertEqual(
            set(RiskAccess.objects.filter(user=user).values_list("role", flat=True)),
            {"risk_officer", "division_head"},
        )
        self.assertFalse(
            RiskAccess.objects.filter(user=user).exclude(division=self.division).exists()
        )
        self.assertEqual(InventoryAccess.objects.get(user=user).role, "officer")
        self.assertTrue(
            ActivityLog.objects.filter(
                action="MEMBER_CREATED", target_id=str(user.pk)
            ).exists()
        )

    def test_member_list_can_sort_names_ascending_and_descending(self):
        get_user_model().objects.create_user(
            username="zulu_user", first_name="Zulu", password="test-password",
            role="employee",
        )
        get_user_model().objects.create_user(
            username="alpha_user", first_name="Alpha", password="test-password",
            role="employee",
        )
        self.client.force_login(self.admin)

        ascending = self.client.get(
            reverse("homepage:member_list") + "?sort=name&direction=asc",
            HTTP_HOST="pwujatim.site",
        )
        descending = self.client.get(
            reverse("homepage:member_list") + "?sort=name&direction=desc",
            HTTP_HOST="pwujatim.site",
        )

        ascending_names = [row["user"].get_full_name() for row in ascending.context["rows"]]
        descending_names = [row["user"].get_full_name() for row in descending.context["rows"]]
        self.assertLess(ascending_names.index("Alpha"), ascending_names.index("Zulu"))
        self.assertLess(descending_names.index("Zulu"), descending_names.index("Alpha"))

    def test_member_admin_cannot_deactivate_own_account(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("homepage:member_edit", args=[self.admin.pk]),
            {
                "username": self.admin.username,
                "first_name": "Farrel",
                "last_name": "MT",
                "email": "farrel@pwujatim.site",
                "phone": "",
                "password": "",
                "password_confirm": "",
                "role": "admin",
                "koperasi_roles": [],
                "risk_roles": [],
                "risk_division": "",
                "inventory_role": "participant",
            },
            HTTP_HOST="pwujatim.site",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tidak dapat menonaktifkan akun sendiri")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_member_admin_can_delete_account_without_disposition_history(self):
        disposable = get_user_model().objects.create_user(
            username="temporary_member",
            password="temporary-password",
            role="employee",
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("homepage:member_delete", args=[disposable.pk]),
            HTTP_HOST="pwujatim.site",
        )

        self.assertRedirects(
            response,
            reverse("homepage:member_list"),
            fetch_redirect_response=False,
        )
        self.assertFalse(get_user_model().objects.filter(pk=disposable.pk).exists())
        self.assertTrue(
            ActivityLog.objects.filter(
                action="MEMBER_DELETED",
                target_id=str(disposable.pk),
            ).exists()
        )

    def test_member_admin_cannot_delete_own_account(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("homepage:member_delete", args=[self.admin.pk]),
            HTTP_HOST="pwujatim.site",
        )

        self.assertRedirects(
            response,
            reverse("homepage:member_edit", args=[self.admin.pk]),
            fetch_redirect_response=False,
        )
        self.assertTrue(get_user_model().objects.filter(pk=self.admin.pk).exists())

    def test_member_admin_can_remove_archive_access(self):
        self.viewer.role = "akuntan"
        self.viewer.save(update_fields=["role"])
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("homepage:member_edit", args=[self.viewer.pk]),
            {
                "username": self.viewer.username,
                "first_name": "",
                "last_name": "",
                "email": self.viewer.email,
                "phone": "",
                "password": "",
                "password_confirm": "",
                "role": "",
                "koperasi_roles": [],
                "risk_roles": [],
                "risk_division": "",
                "inventory_role": "participant",
                "is_active": "on",
            },
            HTTP_HOST="pwujatim.site",
        )

        self.assertRedirects(
            response,
            reverse("homepage:member_list"),
            fetch_redirect_response=False,
        )
        self.viewer.refresh_from_db()
        self.assertEqual(self.viewer.role, "")


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
        for username in ("dirut", "it_pwu", "akuntan1", "akuntan2"):
            with self.subTest(username=username):
                self.assertContains(response, f">{username}<")
        visible_users = get_user_model().objects.count()
        self.assertEqual(len(response.context["directory_rows"]), visible_users)
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
