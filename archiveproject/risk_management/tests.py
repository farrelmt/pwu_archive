from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import Workbook

from accounts.models import ActivityLog

from .models import (
    RiskAccess, RiskActionPlan, RiskDivision, RiskMonitoring, RiskRegister,
    RiskTreatment,
)


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

    def test_template_uses_five_risk_levels(self):
        expected = {
            1: "Sangat Rendah", 2: "Sangat Rendah", 3: "Rendah", 4: "Rendah",
            5: "Sedang", 9: "Sedang", 10: "Tinggi", 16: "Tinggi",
            17: "Sangat Tinggi", 25: "Sangat Tinggi",
        }
        for score, level in expected.items():
            with self.subTest(score=score):
                self.assertEqual(RiskRegister.level_for(score), level)

    def _workbook_upload(self):
        workbook = Workbook()
        identification = workbook.active
        identification.title = "Identifikasi Risiko"
        identification["C4"] = "Divisi A"
        identification["C5"] = "Pemilik A"
        identification["C6"] = "Officer A"
        values = {
            "A10": 1, "B10": "Sasaran strategis", "C10": "Risiko dari workbook",
            "D10": "Indikasi", "E10": "Penyebab", "F10": "Controllable",
            "G10": "Dampak", "H10": 4, "I10": 4,
        }
        for cell, value in values.items():
            identification[cell] = value

        analysis = workbook.create_sheet("Analisis & Evaluasi Risiko")
        values = {
            "A10": 1, "B10": "Risiko dari workbook", "C10": "Kontrol A",
            "E10": "✓", "G10": 3, "H10": 3, "K10": "✓",
        }
        for cell, value in values.items():
            analysis[cell] = value

        treatment = workbook.create_sheet("Perlakuan Risiko")
        values = {
            "A10": 1, "B10": "Risiko dari workbook", "C10": "Mitigasi",
            "D10": "Perbarui SOP", "E10": 2, "F10": 2,
            "I10": "2026-12-31", "J10": "Pemilik A",
        }
        for cell, value in values.items():
            treatment[cell] = value

        monitoring = workbook.create_sheet("Pemantauan TW1")
        values = {
            "A10": 1, "B10": "Risiko dari workbook", "C10": "Perbarui SOP",
            "D10": "Telah dilaksanakan", "E10": "2026-12-31", "F10": "Pemilik A",
            "G10": 3, "H10": 3, "K10": 2, "L10": 2, "O10": 2, "P10": 2,
        }
        for cell, value in values.items():
            monitoring[cell] = value

        stream = BytesIO()
        workbook.save(stream)
        workbook.close()
        return SimpleUploadedFile(
            "Manajemen Risiko 2026.xlsx",
            stream.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_officer_can_import_template_without_duplicates(self):
        self.client.force_login(self.officer)
        for expected_status in (302, 302):
            response = self.client.post(
                reverse("risk:workbook_import"),
                {"workbook": self._workbook_upload()},
                HTTP_HOST="risk.localhost",
            )
            self.assertEqual(response.status_code, expected_status)
        imported = RiskRegister.objects.get(title="Risiko dari workbook")
        self.assertEqual(imported.strategic_objective, "Sasaran strategis")
        self.assertEqual(imported.control_effectiveness, "adequate")
        self.assertTrue(imported.is_priority)
        self.assertEqual(imported.risk_level, "Sedang")
        self.assertEqual(RiskTreatment.objects.filter(risk=imported).count(), 1)
        monitoring = RiskMonitoring.objects.get(risk=imported, year=2026, quarter=1)
        self.assertEqual(monitoring.expected_score, 4)
        self.assertEqual(RiskActionPlan.objects.filter(monitoring=monitoring).count(), 1)

    def test_import_rejects_other_division(self):
        source = Workbook()
        source.active.title = "Identifikasi Risiko"
        source.active["C4"] = "Divisi B"
        stream = BytesIO()
        source.save(stream)
        source.close()
        denied_workbook = SimpleUploadedFile("Risiko 2026.xlsx", stream.getvalue())
        self.client.force_login(self.officer)
        response = self.client.post(
            reverse("risk:workbook_import"), {"workbook": denied_workbook},
            HTTP_HOST="risk.localhost",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tidak memiliki akses impor")

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
        self.assertTrue(ActivityLog.objects.filter(
            actor=self.officer,
            category="RISK",
            action="MONITORING_CREATED",
            target_id=str(monitoring.pk),
        ).exists())

    def test_only_superuser_can_open_risk_activity_log(self):
        self.client.force_login(self.officer)
        denied = self.client.get(
            reverse("risk:activity_log"),
            HTTP_HOST="risk.localhost",
        )
        self.assertEqual(denied.status_code, 403)

        admin = get_user_model().objects.create_superuser(
            username="risk-log-admin",
            password="test-pass-123",
        )
        self.client.force_login(admin)
        response = self.client.get(
            reverse("risk:activity_log"),
            HTTP_HOST="risk.localhost",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log Aktivitas")

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
