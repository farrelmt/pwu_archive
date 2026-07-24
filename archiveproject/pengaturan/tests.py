from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(ALLOWED_HOSTS=["testserver"])
class ProfilePasswordSecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="profile-user",
            password="Existing-password-123",
            role="kadiv_risiko",
            first_name="Profile",
            last_name="User",
            email="profile@example.com",
        )
        self.client.force_login(self.user)
        self.url = reverse("pengaturan:edit-profil", args=[self.user.pk])

    def profile_payload(self, **extra):
        return {
            "first_name": "Profile",
            "last_name": "User",
            "user_email": "profile@example.com",
            **extra,
        }

    def test_password_change_requires_current_password(self):
        response = self.client.post(
            self.url,
            self.profile_payload(
                **{
                    "new-password": "A-new-secure-password-456",
                    "confirm-password": "A-new-secure-password-456",
                }
            ),
            follow=True,
        )

        self.assertContains(response, "Current password is incorrect")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Existing-password-123"))

    def test_common_password_is_rejected_by_django_validators(self):
        response = self.client.post(
            self.url,
            self.profile_payload(
                **{
                    "current-password": "Existing-password-123",
                    "new-password": "password1234",
                    "confirm-password": "password1234",
                }
            ),
            follow=True,
        )

        self.assertContains(response, "too common")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Existing-password-123"))

    def test_secure_password_change_preserves_session(self):
        response = self.client.post(
            self.url,
            self.profile_payload(
                **{
                    "current-password": "Existing-password-123",
                    "new-password": "A-new-secure-password-456",
                    "confirm-password": "A-new-secure-password-456",
                }
            ),
        )

        self.assertRedirects(response, reverse("pengaturan:main"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("A-new-secure-password-456"))
        self.assertIn("_auth_user_id", self.client.session)
