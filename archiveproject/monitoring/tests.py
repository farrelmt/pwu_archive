from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Assignment


@override_settings(
    ROOT_URLCONF="monitoring.host_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class MonitoringTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.creator = User.objects.create_user(username="monitor_test_creator", password="long-test-password", role="employee")
        self.responsible = User.objects.create_user(username="monitor_test_responsible", password="long-test-password", role="employee")
        self.other = User.objects.create_user(username="monitor_test_other", password="long-test-password", role="employee")
        self.assignment = Assignment.objects.create(
            title="Laporan aset", description="Siapkan laporan bulanan",
            month=date(2026, 11, 1), start_date=date(2026, 11, 2), due_date=date(2026, 11, 20),
            division="Divisi Aset", responsible=self.responsible, created_by=self.creator,
        )

    def test_month_and_division_filter_board(self):
        self.client.force_login(self.other)
        url = reverse("monitoring:board")
        shown = self.client.get(url, {"month": "2026-11", "division": "Divisi Aset"}, HTTP_HOST="monitor.localhost")
        self.assertEqual(shown.status_code, 200)
        self.assertContains(shown, "Laporan aset")
        hidden = self.client.get(url, {"month": "2026-12"}, HTTP_HOST="monitor.localhost")
        self.assertNotContains(hidden, "Laporan aset")
        self.assertEqual(self.client.get(url, {"month": "bad"}, HTTP_HOST="monitor.localhost").status_code, 404)

    def test_creator_and_responsible_can_update_status_but_other_cannot(self):
        url = reverse("monitoring:assignment_status", args=[self.assignment.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, {"status": "done"}, HTTP_HOST="monitor.localhost").status_code, 403)
        self.client.force_login(self.responsible)
        self.assertEqual(self.client.get(url, HTTP_HOST="monitor.localhost").status_code, 405)
        self.assertEqual(self.client.post(url, {"status": "doing"}, HTTP_HOST="monitor.localhost").status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, "doing")

    def test_create_validates_dates_and_saves_month(self):
        self.client.force_login(self.creator)
        url = reverse("monitoring:assignment_create")
        payload = {
            "title": "Inventaris baru", "description": "Cek perangkat", "month": "2026-11",
            "start_date": "2026-11-12", "due_date": "2026-11-11",
            "division": "Divisi Aset", "responsible": self.responsible.pk, "status": "todo",
        }
        invalid = self.client.post(url, payload, HTTP_HOST="monitor.localhost")
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, "Tenggat tidak boleh sebelum tanggal mulai")
        payload["due_date"] = "2026-11-25"
        valid = self.client.post(url, payload, HTTP_HOST="monitor.localhost")
        self.assertEqual(valid.status_code, 302)
        created = Assignment.objects.get(title="Inventaris baru")
        self.assertEqual(created.month, date(2026, 11, 1))
        self.assertEqual(created.created_by, self.creator)

    def test_anonymous_is_redirected_to_portal_login(self):
        response = self.client.get(reverse("monitoring:board"), HTTP_HOST="monitor.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    @override_settings(ROOT_URLCONF="archiveproject.urls")
    def test_portal_shows_monitoring_launch(self):
        self.client.force_login(self.other)
        response = self.client.get("/", HTTP_HOST="pwujatim.site")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sistem Monitoring")
        launch = self.client.get(
            reverse("accounts:system_launch", args=["monitoring"]),
            HTTP_HOST="pwujatim.site",
        )
        self.assertEqual(launch.status_code, 302)
        self.assertTrue(launch["Location"].startswith("https://monitor.pwujatim.site/accounts/handoff/"))
