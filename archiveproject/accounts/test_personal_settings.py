from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(ALLOWED_HOSTS=["testserver"], LANDING_HOSTS=["testserver"])
class PersonalSettingsUsernameTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="settings-user")
        self.client.force_login(self.user)
        self.url = reverse("homepage:personal_settings")

    def test_non_superusers_cannot_change_username_even_with_forged_post(self):
        for staff in (False, True):
            with self.subTest(is_staff=staff):
                self.user.is_staff = staff
                self.user.save()
                self.assertNotContains(self.client.get(self.url), 'name="username"')
                response = self.client.post(self.url, {"username": "renamed", "first_name": "Updated"})
                self.assertEqual(response.status_code, 302)
                self.user.refresh_from_db()
                self.assertEqual(self.user.username, "settings-user")
                self.assertEqual(self.user.first_name, "Updated")

    def test_superuser_can_change_username(self):
        self.user.is_superuser = True
        self.user.save()
        self.assertContains(self.client.get(self.url), 'name="username"')
        response = self.client.post(self.url, {"username": "renamed"})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "renamed")

    def test_superuser_cannot_take_existing_username(self):
        self.user.is_superuser = True
        self.user.save()
        get_user_model().objects.create_user(username="existing")
        response = self.client.post(self.url, {"username": "EXISTING"})
        self.assertContains(response, "Username sudah digunakan.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "settings-user")
