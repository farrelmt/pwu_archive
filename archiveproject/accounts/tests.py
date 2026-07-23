from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ActivityLog, SystemUser


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
