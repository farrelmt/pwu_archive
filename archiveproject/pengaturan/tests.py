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

    def test_profile_update_without_new_password_keeps_existing_password(self):
        response = self.client.post(
            self.url,
            self.profile_payload(
                first_name="Updated",
                current_password="Existing-password-123",
            ),
        )

        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertTrue(self.user.check_password("Existing-password-123"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_empty_new_password_ignores_other_password_fields(self):
        response = self.client.post(
            self.url,
            self.profile_payload(
                first_name="Updated",
                current_password="wrong password",
                confirm_password="accidental autofill",
            ),
        )

        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertTrue(self.user.check_password("Existing-password-123"))


@override_settings(
    ALLOWED_HOSTS=["pwujatim.site", "archive.pwujatim.site"],
    LANDING_HOSTS=frozenset({"pwujatim.site"}),
    ARCHIVE_HOSTS=frozenset({"archive.pwujatim.site"}),
    PORTAL_BASE_URL="https://pwujatim.site",
)
class SettingsReturnDestinationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="archive-settings-user",
            password="Existing-password-123",
            role="sekretaris",
        )
        self.client.force_login(self.user)

    def test_archive_settings_link_and_legacy_routes_preserve_origin(self):
        response = self.client.get("/", HTTP_HOST="archive.pwujatim.site")
        self.assertContains(
            response,
            'href="https://pwujatim.site/settings/?from=archive"',
        )
        for path in ("/settings/", "/pengaturan/", f"/pengaturan/edit-profil/{self.user.pk}/"):
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST="archive.pwujatim.site")
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, "https://pwujatim.site/settings/?from=archive")

    def test_back_and_cancel_return_to_archive(self):
        response = self.client.get("/settings/?from=archive", HTTP_HOST="pwujatim.site")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/accounts/system/archive/"', count=2)
        launch_response = self.client.get(
            "/accounts/system/archive/", HTTP_HOST="pwujatim.site"
        )
        self.assertEqual(launch_response.status_code, 302)
        self.assertTrue(
            launch_response.url.startswith(
                "https://archive.pwujatim.site/accounts/handoff/"
            )
        )

    def test_archive_referrer_is_kept_when_link_has_no_origin(self):
        response = self.client.get(
            "/settings/",
            HTTP_HOST="pwujatim.site",
            HTTP_REFERER="https://archive.pwujatim.site/",
        )
        self.assertContains(response, 'href="/accounts/system/archive/"', count=2)

        response = self.client.post(
            "/settings/",
            {"first_name": "Updated"},
            HTTP_HOST="pwujatim.site",
            HTTP_REFERER="https://pwujatim.site/settings/",
        )
        self.assertRedirects(
            response, "/settings/?from=archive", fetch_redirect_response=False
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertTrue(self.user.check_password("Existing-password-123"))

    def test_portal_settings_link_clears_previous_archive_return(self):
        self.client.get(
            "/settings/",
            HTTP_HOST="pwujatim.site",
            HTTP_REFERER="https://archive.pwujatim.site/",
        )
        response = self.client.get(
            "/settings/",
            HTTP_HOST="pwujatim.site",
            HTTP_REFERER="https://pwujatim.site/",
        )
        self.assertContains(response, 'href="/"', count=2)

    def test_profile_save_keeps_archive_return_destination_and_password(self):
        response = self.client.post(
            "/settings/?from=archive",
            {"first_name": "Updated"},
            HTTP_HOST="pwujatim.site",
        )

        self.assertRedirects(
            response,
            "/settings/?from=archive",
            fetch_redirect_response=False,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertTrue(self.user.check_password("Existing-password-123"))

    def test_untrusted_or_inaccessible_origin_returns_to_portal(self):
        for origin in ("https://evil.example/", "inventory"):
            with self.subTest(origin=origin):
                response = self.client.get(
                    "/settings/", {"from": origin}, HTTP_HOST="pwujatim.site"
                )
                self.assertContains(response, 'href="/"', count=2)
