from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    LANDING_HOSTS=frozenset({"testserver"}),
)
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
        self.url = reverse("homepage:personal_settings")

    def profile_payload(self, **extra):
        return {
            "first_name": "Profile",
            "last_name": "User",
            "email": "profile@example.com",
            "phone": "08123456789",
            **extra,
        }

    def test_password_change_requires_current_password(self):
        response = self.client.post(
            self.url,
            self.profile_payload(
                **{
                    "new_password": "A-new-secure-password-456",
                    "confirm_password": "A-new-secure-password-456",
                }
            ),
            follow=True,
        )

        self.assertContains(response, "Password saat ini tidak benar")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Existing-password-123"))

    def test_common_password_is_rejected_by_django_validators(self):
        response = self.client.post(
            self.url,
            self.profile_payload(
                **{
                    "current_password": "Existing-password-123",
                    "new_password": "password1234",
                    "confirm_password": "password1234",
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
                    "current_password": "Existing-password-123",
                    "new_password": "A-new-secure-password-456",
                    "confirm_password": "A-new-secure-password-456",
                }
            ),
        )

        self.assertRedirects(response, reverse("homepage:personal_settings"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("A-new-secure-password-456"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_user_can_only_edit_personal_information_not_role_or_username(self):
        response = self.client.post(
            self.url,
            {
                "first_name": "Updated",
                "last_name": "Name",
                "email": "updated@pwujatim.site",
                "phone": "089999999",
                "username": "attempted-change",
                "role": "admin",
            },
        )

        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.phone, "089999999")
        self.assertEqual(self.user.username, "profile-user")
        self.assertEqual(self.user.role, "kadiv_risiko")
