from django.test import TestCase, override_settings
from django.urls import reverse

from .models import SystemUser


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
