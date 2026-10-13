from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import ActivityLog, SystemUser


class SharedProfileSignalTests(TestCase):
    def setUp(self):
        self.user = SystemUser.objects.create_user(
            username="profile-signal-user",
            password="password-for-tests",
            role="employee",
        )

    @patch("inventory.services.sync_company_member")
    def test_last_login_update_does_not_sync_inventory_profile(self, sync_profile):
        self.user.last_login = timezone.now()
        self.user.save(update_fields=["last_login"])

        sync_profile.assert_not_called()

    @patch("inventory.services.sync_company_member")
    def test_profile_update_still_syncs_inventory_profile(self, sync_profile):
        self.user.first_name = "Updated"
        self.user.save(update_fields=["first_name"])

        sync_profile.assert_called_once_with(self.user)


class SystemUserEmailTests(TestCase):
    def test_empty_email_remains_empty(self):
        user = SystemUser.objects.create_user(
            username="placeholder-email-user",
            password="password-for-tests",
            role="kadiv",
        )

        self.assertEqual(user.email, "")
        self.assertEqual(
            SystemUser.objects.get(pk=user.pk).email,
            "",
        )


@override_settings(ALLOWED_HOSTS=["testserver"])
class LogoutSecurityTests(TestCase):
    def setUp(self):
        self.user = SystemUser.objects.create_user(
            username="user",
            password="password-for-tests",
            role="kadiv",
        )
        self.client.force_login(self.user)

    def test_logout_rejects_get(self):
        response = self.client.get(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_accepts_post(self):
        response = self.client.post(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://pwujatim.site/accounts/login/")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(
            ActivityLog.objects.filter(
                actor_username="user",
                category="AUTH",
                action="LOGOUT",
                success=True,
            ).exists()
        )

    @override_settings(
        ALLOWED_HOSTS=[
            "pwujatim.site", "archive.pwujatim.site", "koperasi.pwujatim.site",
            "risk.pwujatim.site", "inventory.pwujatim.site",
        ],
        LANDING_HOSTS=frozenset({"pwujatim.site"}),
        ARCHIVE_HOSTS=frozenset({"archive.pwujatim.site"}),
        KOPERASI_HOSTS=frozenset({"koperasi.pwujatim.site"}),
        RISK_HOSTS=frozenset({"risk.pwujatim.site"}),
        INVENTORY_HOSTS=frozenset({"inventory.pwujatim.site"}),
        PORTAL_BASE_URL="https://pwujatim.site",
    )
    def test_logout_from_every_system_clears_shared_session(self):
        from koperasi.models import KoperasiAccess

        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=["is_superuser", "is_staff"])
        KoperasiAccess.objects.create(
            user=self.user,
            company=None,
            role="admin",
            is_active=True,
        )

        for hostname in (
            "archive.pwujatim.site",
            "koperasi.pwujatim.site",
            "risk.pwujatim.site",
            "inventory.pwujatim.site",
        ):
            with self.subTest(hostname=hostname):
                self.client.force_login(self.user)
                response = self.client.post(
                    "/accounts/logout/",
                    HTTP_HOST=hostname,
                )

                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    response["Location"],
                    "https://pwujatim.site/accounts/login/",
                )
                self.assertNotIn("_auth_user_id", self.client.session)
                self.assertEqual(response.cookies["sessionid"]["domain"], ".pwujatim.site")


@override_settings(ALLOWED_HOSTS=["testserver"])
class AuthenticationAuditTests(TestCase):
    def setUp(self):
        self.user = SystemUser.objects.create_user(
            username="audited-user",
            password="password-for-tests",
            role="kadiv",
        )

    def test_successful_login_is_audited_with_request_metadata(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "audited-user",
                "password": "password-for-tests",
            },
            REMOTE_ADDR="192.0.2.10",
            HTTP_USER_AGENT="Audit Test Browser",
        )

        self.assertRedirects(response, reverse("homepage:dashboard"))
        log = ActivityLog.objects.get(action="LOGIN")
        self.assertEqual(log.actor, self.user)
        self.assertEqual(log.actor_username, "audited-user")
        self.assertEqual(str(log.ip_address), "192.0.2.10")
        self.assertEqual(log.user_agent, "Audit Test Browser")
        self.assertTrue(log.success)

    def test_failed_login_does_not_store_password(self):
        self.client.post(
            reverse("accounts:login"),
            {
                "username": "audited-user",
                "password": "highly-sensitive-password",
            },
        )

        log = ActivityLog.objects.get(action="LOGIN_FAILED")
        self.assertEqual(log.actor_username, "audited-user")
        self.assertFalse(log.success)
        self.assertNotIn("highly-sensitive-password", log.description)
        self.assertNotIn("highly-sensitive-password", str(log.metadata))

    def test_login_ignores_forbidden_create_page_next_url(self):
        response = self.client.post(
            f'{reverse("accounts:login")}?next=/disposisi/tambah/',
            {
                "username": "audited-user",
                "password": "password-for-tests",
                "next": "/disposisi/tambah/",
            },
        )

        self.assertRedirects(response, reverse("homepage:dashboard"))

    def test_login_ignores_forbidden_full_archive_list_next_url(self):
        response = self.client.post(
            f'{reverse("accounts:login")}?next=/disposisi/',
            {
                "username": "audited-user",
                "password": "password-for-tests",
                "next": "/disposisi/",
            },
        )

        self.assertRedirects(response, reverse("homepage:dashboard"))

    def test_editor_login_keeps_allowed_create_page_next_url(self):
        editor = SystemUser.objects.create_user(
            username="archive-editor",
            password="password-for-tests",
            role="sekretaris",
        )
        response = self.client.post(
            f'{reverse("accounts:login")}?next=/disposisi/tambah/',
            {
                "username": editor.username,
                "password": "password-for-tests",
                "next": "/disposisi/tambah/",
            },
        )

        self.assertRedirects(response, reverse("disposisi:tambahdisposisi"))

    def test_editor_login_keeps_allowed_full_archive_list_next_url(self):
        editor = SystemUser.objects.create_user(
            username="archive-list-editor",
            password="password-for-tests",
            role="sekretaris",
        )
        response = self.client.post(
            f'{reverse("accounts:login")}?next=/disposisi/',
            {
                "username": editor.username,
                "password": "password-for-tests",
                "next": "/disposisi/",
            },
        )

        self.assertRedirects(response, reverse("disposisi:disposisi"))


@override_settings(ALLOWED_HOSTS=["testserver"])
class LoginSecurityTests(TestCase):
    def test_login_response_has_enforced_csp(self):
        response = self.client.get(reverse("accounts:login"))

        policy = response["Content-Security-Policy"]
        self.assertIn("script-src 'self' 'nonce-", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertNotIn("unsafe-inline", policy.split("style-src")[0])
        self.assertEqual(
            response["Permissions-Policy"],
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )

    @override_settings(ALLOWED_HOSTS=["localhost"])
    def test_localhost_does_not_force_https_for_system_subdomains(self):
        response = self.client.get(
            reverse("accounts:login"),
            HTTP_HOST="localhost:8000",
        )

        self.assertNotIn(
            "upgrade-insecure-requests",
            response["Content-Security-Policy"],
        )

    @override_settings(ALLOWED_HOSTS=["pwujatim.site"])
    def test_production_domain_still_upgrades_insecure_requests(self):
        response = self.client.get(
            reverse("accounts:login"),
            HTTP_HOST="pwujatim.site",
        )

        self.assertIn(
            "upgrade-insecure-requests",
            response["Content-Security-Policy"],
        )


@override_settings(
    ALLOWED_HOSTS=["localhost", "archive.localhost", "koperasi.localhost"],
    LANDING_HOSTS=frozenset({"localhost"}),
    ARCHIVE_HOSTS=frozenset({"archive.localhost"}),
    KOPERASI_HOSTS=frozenset({"koperasi.localhost"}),
    PORTAL_BASE_URL="https://pwujatim.site",
)
class LoginThemeTests(TestCase):
    def test_central_portal_login_uses_blue_theme(self):
        response = self.client.get(
            "/accounts/login/",
            HTTP_HOST="localhost",
        )

        self.assertContains(response, "bg-blue-950")
        self.assertContains(response, "bg-blue-950 shadow-blue-950/15")
        self.assertNotContains(response, "bg-green-950")
        self.assertContains(response, "Portal Sistem Informasi PWU Jatim")

    def test_login_form_recovers_after_browser_restores_page(self):
        response = self.client.get(
            "/accounts/login/",
            HTTP_HOST="localhost",
        )

        self.assertContains(response, 'window.addEventListener("pageshow", event =>')
        self.assertContains(response, 'loginSubmit.removeAttribute("aria-disabled")')
        self.assertContains(response, 'credentials: "same-origin"')
        self.assertContains(response, "window.location.replace(status.destination)")
        self.assertContains(response, "window.setTimeout(retryLoginNavigation, 20000)")
        self.assertNotContains(response, "window.location.reload()")
        self.assertNotContains(response, "loginSubmit.disabled = true")

    def test_login_recovery_waits_for_authenticated_session(self):
        status_url = reverse("accounts:login_status")
        guest = self.client.get(status_url, HTTP_HOST="localhost")
        self.assertEqual(guest.json(), {"authenticated": False})
        self.assertIn("no-store", guest["Cache-Control"])
        self.assertEqual(
            self.client.post(status_url, HTTP_HOST="localhost").status_code,
            405,
        )

        user = SystemUser.objects.create_user(
            username="login-recovery-user",
            password="password-for-tests",
            role="kadiv_keuangan",
        )
        archive_url = "http://archive.localhost/monitor/?status=DIBAGIKAN"
        login_response = self.client.post(
            reverse("accounts:login"),
            {
                "username": user.username,
                "password": "password-for-tests",
                "next": archive_url,
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(login_response.status_code, 302)

        status = self.client.get(
            status_url,
            {"next": archive_url},
            HTTP_HOST="localhost",
        )
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json(), {
            "authenticated": True,
            "destination": login_response["Location"],
        })
        self.assertIn("no-store", status["Cache-Control"])

        unsafe = self.client.get(
            status_url,
            {"next": "https://untrusted.example/"},
            HTTP_HOST="localhost",
        )
        self.assertEqual(unsafe.json()["destination"], reverse("homepage:dashboard"))

    @override_settings(
        ALLOWED_HOSTS=["pwujatim.site", "archive.pwujatim.site"],
        LANDING_HOSTS=frozenset({"pwujatim.site"}),
        ARCHIVE_HOSTS=frozenset({"archive.pwujatim.site"}),
    )
    def test_production_login_recovery_uses_shared_session_and_safe_destination(self):
        user = SystemUser.objects.create_user(
            username="production-recovery-user",
            password="password-for-tests",
            role="kadiv_keuangan",
        )
        archive_url = "https://archive.pwujatim.site/monitor/"
        request_headers = {
            "HTTP_HOST": "pwujatim.site",
            "HTTP_X_FORWARDED_PROTO": "https",
        }
        login_response = self.client.post(
            reverse("accounts:login"),
            {
                "username": user.username,
                "password": "password-for-tests",
                "next": archive_url,
            },
            **request_headers,
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response.cookies["sessionid"]["domain"], ".pwujatim.site")

        status = self.client.get(
            reverse("accounts:login_status"),
            {"next": archive_url},
            **request_headers,
        )
        self.assertEqual(status.json(), {
            "authenticated": True,
            "destination": login_response["Location"],
        })

    def test_system_subdomain_login_redirects_to_central_portal(self):
        response = self.client.get(
            "/accounts/login/",
            HTTP_HOST="koperasi.localhost",
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("http://localhost/accounts/login/"))
        self.assertIn("koperasi.localhost", response["Location"])

    def test_archive_login_uses_same_origin_launch_then_archive_handoff(self):
        user = SystemUser.objects.create_user(
            username="archive-login-handoff",
            password="password-for-tests",
            role="kadiv_keuangan",
        )
        archive_url = "http://archive.localhost/monitor/?status=DIBAGIKAN"

        login_response = self.client.post(
            "/accounts/login/",
            {
                "username": user.username,
                "password": "password-for-tests",
                "next": archive_url,
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(
            login_response["Location"],
            "/accounts/system/archive/?next=%2Fmonitor%2F%3Fstatus%3DDIBAGIKAN",
        )

        launch_response = self.client.get(
            login_response["Location"],
            HTTP_HOST="localhost",
        )
        self.assertEqual(launch_response.status_code, 302)
        self.assertTrue(
            launch_response["Location"].startswith(
                "http://archive.localhost/accounts/handoff/?token="
            )
        )

        handoff_path = launch_response["Location"].split(
            "archive.localhost", 1
        )[1]
        handoff_response = self.client.get(
            handoff_path,
            HTTP_HOST="archive.localhost",
        )
        self.assertEqual(handoff_response.status_code, 302)
        self.assertEqual(
            handoff_response["Location"],
            "/monitor/?status=DIBAGIKAN",
        )

    def test_authenticated_login_reload_keeps_archive_destination(self):
        user = SystemUser.objects.create_user(
            username="archive-login-retry",
            password="password-for-tests",
            role="kadiv_keuangan",
        )
        self.client.force_login(user)

        response = self.client.get(
            "/accounts/login/?next=http%3A%2F%2Farchive.localhost%2F",
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "/accounts/system/archive/?next=%2F",
        )

    def test_failed_login_preserves_archive_destination(self):
        archive_url = "http://archive.localhost/"

        response = self.client.post(
            "/accounts/login/",
            {
                "username": "missing-user",
                "password": "incorrect-password",
                "next": archive_url,
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<input type="hidden" name="next" value="{archive_url}">',
            html=True,
        )

    def test_central_login_cannot_continue_to_koperasi_without_role(self):
        user = SystemUser.objects.create_user(
            username="koperasi-login-test",
            password="password-for-tests",
            role="akuntan",
        )

        response = self.client.post(
            "/accounts/login/?next=http://koperasi.localhost/",
            {
                "username": user.username,
                "password": "password-for-tests",
                "next": "http://koperasi.localhost/",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("homepage:dashboard"))
        self.assertEqual(self.client.cookies["sessionid"]["domain"], "")

    def test_central_login_can_continue_to_koperasi_with_role(self):
        from koperasi.models import KoperasiAccess

        user = SystemUser.objects.create_user(
            username="koperasi-authorized-login-test",
            password="password-for-tests",
            role="akuntan",
        )
        KoperasiAccess.objects.create(user=user, role="auditor")

        response = self.client.post(
            "/accounts/login/?next=http://koperasi.localhost/",
            {
                "username": user.username,
                "password": "password-for-tests",
                "next": "http://koperasi.localhost/",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://koperasi.localhost/")
