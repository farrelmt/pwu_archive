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
