from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import RiskAccess, RiskActionPlan, RiskDivision, RiskMonitoring, RiskRegister


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}, ROOT_URLCONF="risk_management.host_urls")
class RiskPermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.division_a = RiskDivision.objects.create(code="A", name="Divisi A")
        self.division_b = RiskDivision.objects.create(code="B", name="Divisi B")
        self.officer = User.objects.create_user(username="officer", password="test-pass-123", role="risk")
        self.head = User.objects.create_user(username="head", password="test-pass-123", role="risk")
        RiskAccess.objects.create(user=self.officer, role="risk_officer", division=self.division_a)
        RiskAccess.objects.create(user=self.head, role="division_head", division=self.division_a)
        self.risk = RiskRegister.objects.create(
            division=self.division_a, title="Gangguan operasional", category="operational",
            description="Uraian", cause="Penyebab", impact="Dampak",
            inherent_likelihood=4, inherent_impact=4, existing_controls="Kontrol",
            mitigation_plan="Mitigasi", risk_owner="Pemilik", residual_likelihood=2,
            residual_impact=3, status="mitigating", created_by=self.officer, updated_by=self.officer,
        )

    def test_officer_can_edit_own_division(self):
        self.client.force_login(self.officer)
        response = self.client.get(reverse("risk:risk_edit", args=[self.risk.pk]), HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)

    def test_division_head_is_read_only(self):
        self.client.force_login(self.head)
        response = self.client.get(reverse("risk:risk_edit", args=[self.risk.pk]), HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 403)

    def test_division_head_cannot_see_other_division(self):
        other = RiskRegister.objects.create(
            division=self.division_b, title="Risiko lain", category="financial",
            description="Uraian", cause="Penyebab", impact="Dampak",
            inherent_likelihood=3, inherent_impact=3, risk_owner="Pemilik",
            residual_likelihood=2, residual_impact=2, created_by=self.officer, updated_by=self.officer,
        )
        self.client.force_login(self.head)
        response = self.client.get(reverse("risk:risk_detail", args=[other.pk]), HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 404)

    def test_risk_score_and_level(self):
        self.assertEqual(self.risk.inherent_score, 16)
        self.assertEqual(self.risk.residual_score, 6)
        self.assertEqual(self.risk.risk_level, "Sedang")

    def test_officer_can_record_quarterly_monitoring(self):
        self.client.force_login(self.officer)
        response = self.client.post(
            reverse("risk:monitoring_create", args=[self.risk.pk]),
            {
                "year": 2026, "quarter": 2,
                "initial_likelihood": 4, "initial_impact": 4,
                "final_likelihood": 3, "final_impact": 3,
                "business_environment_changes": "Tidak ada perubahan material.",
                "evaluation_notes": "Mitigasi berjalan.",
            },
            HTTP_HOST="risk.localhost",
        )
        self.assertEqual(response.status_code, 302)
        monitoring = RiskMonitoring.objects.get(risk=self.risk, year=2026, quarter=2)
        self.assertEqual(monitoring.initial_score, 16)
        self.assertEqual(monitoring.final_score, 9)
        self.assertEqual(monitoring.score_reduction, 7)

    def test_monitoring_report_summarizes_actions_and_scores(self):
        monitoring = RiskMonitoring.objects.create(
            risk=self.risk, year=2026, quarter=2,
            initial_likelihood=4, initial_impact=4,
            final_likelihood=3, final_impact=3,
            updated_by=self.officer,
        )
        RiskActionPlan.objects.create(
            monitoring=monitoring,
            description="Perbarui prosedur pengendalian.",
            responsible_person="Pemilik",
            realization="Prosedur telah diperbarui.",
            realization_date="2026-06-30",
            progress=100,
            status="completed",
            created_by=self.officer,
            updated_by=self.officer,
        )
        self.client.force_login(self.officer)
        response = self.client.get(
            reverse("risk:monitoring_report"),
            {"year": 2026, "quarter": 2},
            HTTP_HOST="risk.localhost",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["totals"]["risk_count"], 1)
        self.assertEqual(response.context["totals"]["plan_count"], 1)
        self.assertEqual(response.context["totals"]["realized_count"], 1)
        self.assertEqual(response.context["totals"]["realization_percent"], 100)
        self.assertEqual(response.context["totals"]["score_reduction"], 7)
