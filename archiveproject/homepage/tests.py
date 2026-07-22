from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model


@override_settings(ALLOWED_HOSTS=["testserver"])
class HomepageAuthenticationTests(TestCase):
    def test_feature_pages_require_login(self):
        for name in ("notadinas", "suratkeluar", "monitor", "divisi", "notif"):
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
            role="sekretaris",
        )
        self.finance_head = user_model.objects.create_user(
            username="kadiv_keuangan_test",
            password="test-password",
            role="kadiv_keuangan",
            is_active=False,
        )

    def test_division_page_lists_all_users_and_their_roles(self):
        self.client.force_login(self.secretary)

        response = self.client.get(reverse("homepage:divisi"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sekretaris_test")
        self.assertContains(response, "Siti Sekretaris")
        self.assertContains(response, "Sekretaris")
        self.assertContains(response, "kadiv_keuangan_test")
        self.assertContains(response, "Kepala Divisi Keuangan")
        self.assertContains(response, "Nonaktif")
        total_users = get_user_model().objects.count()
        self.assertEqual(response.context["users"].count(), total_users)
        self.assertContains(response, f"Total pengguna: {total_users}")
