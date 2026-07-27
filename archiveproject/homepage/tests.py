from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from accounts.models import ActivityLog


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

    def test_non_editor_cannot_list_user_directory(self):
        viewer = get_user_model().objects.create_user(
            username="viewer_test",
            password="test-password",
            role="kadiv_risiko",
        )
        self.client.force_login(viewer)

        response = self.client.get(reverse("homepage:divisi"))

        self.assertEqual(response.status_code, 403)


@override_settings(ALLOWED_HOSTS=["testserver"])
class ActivityLogAccessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            username="audit-admin",
            password="test-password",
            role="admin",
        )
        self.regular_user = user_model.objects.create_user(
            username="audit-viewer",
            password="test-password",
            role="kadiv_keuangan",
        )
        ActivityLog.objects.create(
            actor=self.regular_user,
            actor_username=self.regular_user.username,
            category="DISPOSISI",
            action="DIEDIT",
            description="Disposition updated.",
            target_type="disposisi.Disposisi",
            target_id="12",
            target_label="12/VII/2026",
        )

    def test_activity_log_is_visible_to_admin(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("homepage:activity_log"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Activity Log")
        self.assertContains(response, "audit-viewer")
        self.assertContains(response, "DIEDIT")
        self.assertContains(response, "12/VII/2026")

    def test_activity_log_rejects_non_admin(self):
        self.client.force_login(self.regular_user)

        response = self.client.get(reverse("homepage:activity_log"))

        self.assertEqual(response.status_code, 403)

    def test_activity_log_filters_by_category_and_result(self):
        ActivityLog.objects.create(
            actor_username="unknown-user",
            category="AUTH",
            action="LOGIN_FAILED",
            description="Login attempt failed.",
            success=False,
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("homepage:activity_log"),
            {"category": "AUTH", "result": "failed"},
        )

        self.assertContains(response, "LOGIN_FAILED")
        self.assertNotContains(response, "12/VII/2026")
