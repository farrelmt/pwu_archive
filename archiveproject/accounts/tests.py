from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ActivityLog, SystemUser


class SystemUserEmailTests(TestCase):
    def test_empty_email_uses_testing_placeholder(self):
        user = SystemUser.objects.create_user(
            username="placeholder-email-user",
            password="password-for-tests",
            role="kadiv",
        )

        self.assertEqual(user.email, "it.pwujatim@gmail.com")
        self.assertEqual(
            SystemUser.objects.get(pk=user.pk).email,
            "it.pwujatim@gmail.com",
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

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(
            ActivityLog.objects.filter(
                actor_username="user",
                category="AUTH",
                action="LOGOUT",
                success=True,
            ).exists()
        )


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


@override_settings(
    ALLOWED_HOSTS=["archive.localhost", "koperasi.localhost"],
    KOPERASI_HOSTS=frozenset({"koperasi.localhost"}),
)
class LoginThemeTests(TestCase):
    def test_archive_login_uses_blue_theme(self):
        response = self.client.get(
            "/accounts/login/",
            HTTP_HOST="archive.localhost",
        )

        self.assertContains(response, "bg-blue-950")
        self.assertContains(response, "bg-blue-950 shadow-blue-950/15")
        self.assertNotContains(response, "bg-green-950")

    def test_koperasi_login_uses_green_theme(self):
        response = self.client.get(
            "/accounts/login/",
            HTTP_HOST="koperasi.localhost",
        )

        self.assertContains(response, "bg-green-950")
        self.assertContains(response, "bg-green-800 shadow-green-950/20")
        self.assertNotContains(response, "bg-blue-950")

    def test_koperasi_user_can_login_with_isolated_url_configuration(self):
        user = SystemUser.objects.create_user(
            username="koperasi-login-test",
            password="password-for-tests",
            role="akuntan",
        )

        response = self.client.post(
            "/accounts/login/?next=/",
            {
                "username": user.username,
                "password": "password-for-tests",
                "next": "/",
            },
            HTTP_HOST="koperasi.localhost",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
