from datetime import datetime
from io import BytesIO
from xml.etree import ElementTree

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from zipfile import ZipFile

from accounts.models import ActivityLog

from .models import (
    RiskAccess, RiskActionPlan, RiskCodeSequence, RiskControl, RiskDivision, RiskMonitoring, RiskRegister,
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
        self.assertContains(response, 'id="deleteRiskForm"')
        self.assertContains(response, '+ Tambah Opsi')

    def test_officer_can_delete_own_risk_with_treatments(self):
        RiskTreatment.objects.create(risk=self.risk, action_plan="Rencana", created_by=self.officer, updated_by=self.officer)
        self.client.force_login(self.officer)
        url = reverse("risk:risk_delete", args=[self.risk.pk])
        self.assertEqual(self.client.get(url, HTTP_HOST="risk.localhost").status_code, 405)
        response = self.client.post(url, HTTP_HOST="risk.localhost")
        self.assertRedirects(response, reverse("risk:risk_list"), fetch_redirect_response=False)
        self.assertFalse(RiskRegister.objects.filter(pk=self.risk.pk).exists())
        self.assertFalse(RiskTreatment.objects.filter(risk_id=self.risk.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(action="RISK_DELETED", target_id=str(self.risk.pk)).exists())

    def test_read_only_user_cannot_delete_risk(self):
        self.client.force_login(self.head)
        response = self.client.post(reverse("risk:risk_delete", args=[self.risk.pk]), HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(RiskRegister.objects.filter(pk=self.risk.pk).exists())

    def test_division_list_and_new_risk_only_offer_active_divisions(self):
        manager = get_user_model().objects.create_user(username="division-manager", role="risk")
        RiskAccess.objects.create(user=manager, role="manager_member")
        self.division_b.is_active = False
        self.division_b.save(update_fields=["is_active"])
        self.client.force_login(manager)

        listing = self.client.get(reverse("risk:divisions"), HTTP_HOST="risk.localhost")
        self.assertEqual(listing.status_code, 200)
        self.assertIn("Divisi KSO", [division.name for division in listing.context["divisions"]])
        self.assertNotIn(self.division_b, listing.context["divisions"])
        self.assertIn("Sekretaris Perusahaan", [division.name for division in listing.context["divisions"]])
        self.assertFalse(RiskDivision.objects.get(code="OPS").is_active)
        self.assertFalse(RiskDivision.objects.get(code="SDM").is_active)
        self.assertFalse(RiskDivision.objects.get(code="TI").is_active)

        create = self.client.get(reverse("risk:risk_create"), HTTP_HOST="risk.localhost")
        choices = create.context["form"].fields["division"].queryset
        self.assertIn(RiskDivision.objects.get(code="KSO"), choices)
        self.assertNotIn(self.division_b, choices)
        self.assertNotIn(RiskDivision.objects.get(code="OPS"), choices)

    def test_existing_risk_can_keep_division_after_it_is_deactivated(self):
        self.division_a.is_active = False
        self.division_a.save(update_fields=["is_active"])
        self.client.force_login(self.officer)
        edit = self.client.get(reverse("risk:risk_edit", args=[self.risk.pk]), HTTP_HOST="risk.localhost")
        self.assertEqual(edit.status_code, 200)
        self.assertIn(self.division_a, edit.context["form"].fields["division"].queryset)

    def test_sop_codes_increment_across_categories_per_kind_and_division(self):
        self.assertEqual(self.risk.risk_code, "B/A/010/001")

        def create_risk(**coding):
            return RiskRegister.objects.create(
                division=coding.pop("division", self.division_a),
                title="Risiko kode SOP", category="operational", description="Uraian",
                cause="Sebab", impact="Dampak", risk_owner="Owner",
                created_by=self.officer, updated_by=self.officer, **coding,
            )

        self.assertEqual(create_risk().risk_code, "B/A/010/002")
        self.assertEqual(create_risk(code_category="001").risk_code, "B/A/001/003")
        self.assertEqual(create_risk(risk_kind="A", risk_source="01", code_category="006").risk_code, "A/A/006/001")
        self.assertEqual(create_risk(risk_kind="A", risk_source="02", code_category="006").risk_code, "A/A/006/002")
        mri, _ = RiskDivision.objects.get_or_create(code="MRI", defaults={"name": "Manajemen Risiko"})
        first = create_risk(division=mri, risk_kind="A", risk_source="01", code_category="003")
        second = create_risk(division=mri, risk_kind="A", risk_source="02", code_category="003")
        self.assertEqual(first.risk_code, "A/MRI/003/001")
        self.assertEqual(second.risk_code, "A/MRI/003/002")
        second.delete()
        self.assertEqual(
            create_risk(division=mri, risk_kind="A", risk_source="01", code_category="003").risk_code,
            "A/MRI/003/002",
        )
        project = create_risk(division=RiskDivision.objects.get(code="KSO"), risk_kind="C", code_category="003")
        self.assertEqual(project.risk_code, "C/KSO/003/001")
        project.code_category = "010"
        project.save()
        self.assertEqual(project.risk_code, "C/KSO/010/001")
        project.save()
        self.assertEqual(project.risk_code, "C/KSO/010/001")
        self.assertEqual(
            create_risk(division=RiskDivision.objects.get(code="KSO"), risk_kind="C", code_category="003").risk_code,
            "C/KSO/003/002",
        )
        self.assertEqual(create_risk(division=self.division_b).risk_code, "B/B/010/001")

    def test_deleting_middle_risk_closes_gap_in_its_code_series(self):
        def create_risk():
            return RiskRegister.objects.create(
                division=self.division_a, title="Risiko urutan", category="operational",
                description="Uraian", cause="Sebab", impact="Dampak", risk_owner="Owner",
                created_by=self.officer, updated_by=self.officer,
            )

        middle = create_risk()
        last = create_risk()
        other_category = RiskRegister.objects.create(
            division=self.division_a, title="Risiko kategori lain", category="operational",
            code_category="003", description="Uraian", cause="Sebab", impact="Dampak",
            risk_owner="Owner", created_by=self.officer, updated_by=self.officer,
        )
        self.assertEqual(last.risk_code, "B/A/010/003")

        self.client.force_login(self.officer)
        response = self.client.post(reverse("risk:risk_delete", args=[middle.pk]), HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        last.refresh_from_db()
        other_category.refresh_from_db()
        self.assertEqual(last.risk_code, "B/A/010/002")
        self.assertEqual(other_category.risk_code, "B/A/003/003")
        self.assertEqual(RiskCodeSequence.objects.get(prefix="B/A").last_number, 3)
        self.assertEqual(create_risk().risk_code, "B/A/010/004")

    def test_existing_codes_are_renumbered_across_categories_by_migration(self):
        from importlib import import_module
        from types import SimpleNamespace

        from django.apps import apps
        from django.db import connection

        number_risks_across_categories = import_module(
            "risk_management.migrations.0017_division_wide_risk_sequence"
        ).number_risks_across_categories
        second = RiskRegister.objects.create(
            division=self.division_a, title="Risiko kedua", category="operational",
            description="Uraian", cause="Sebab", impact="Dampak", risk_owner="Owner",
            created_by=self.officer, updated_by=self.officer,
        )
        third = RiskRegister.objects.create(
            division=self.division_a, title="Risiko kategori lain", category="operational",
            code_category="003", description="Uraian", cause="Sebab", impact="Dampak",
            risk_owner="Owner", created_by=self.officer, updated_by=self.officer,
        )
        RiskRegister.objects.filter(pk=second.pk).update(risk_code="B/A/010/004")
        RiskRegister.objects.filter(pk=third.pk).update(risk_code="B/A/003/001")
        RiskCodeSequence.objects.filter(prefix="B/A").update(last_number=9)

        number_risks_across_categories(apps, SimpleNamespace(connection=connection))
        second.refresh_from_db()
        third.refresh_from_db()
        self.assertEqual(second.risk_code, "B/A/010/002")
        self.assertEqual(third.risk_code, "B/A/003/003")
        self.assertEqual(RiskCodeSequence.objects.get(prefix="B/A").last_number, 3)

    def test_admin_bulk_delete_compacts_remaining_codes(self):
        from django.contrib import admin

        from .admin import RiskRegisterAdmin

        def create_risk():
            return RiskRegister.objects.create(
                division=self.division_a, title="Risiko admin", category="operational",
                description="Uraian", cause="Sebab", impact="Dampak", risk_owner="Owner",
                created_by=self.officer, updated_by=self.officer,
            )

        middle = create_risk()
        last = create_risk()
        RiskRegisterAdmin(RiskRegister, admin.site).delete_queryset(
            None, RiskRegister.objects.filter(pk__in=[self.risk.pk, middle.pk]),
        )
        last.refresh_from_db()
        self.assertEqual(last.risk_code, "B/A/010/001")
        self.assertEqual(RiskCodeSequence.objects.get(prefix="B/A").last_number, 1)

    def test_old_strategic_codes_migrate_to_division_sequence(self):
        from importlib import import_module
        from types import SimpleNamespace

        from django.apps import apps
        from django.db import connection

        use_division_in_strategic_codes = import_module(
            "risk_management.migrations.0015_strategic_division_codes"
        ).use_division_in_strategic_codes

        mri, _ = RiskDivision.objects.get_or_create(code="MRI", defaults={"name": "Manajemen Risiko"})
        risks = []
        for source in ("01", "02"):
            risk = RiskRegister.objects.create(
                division=mri, risk_kind="A", risk_source=source, code_category="003",
                title=f"Risiko strategis {source}", category="strategic",
                description="Uraian", cause="Sebab", impact="Dampak",
                risk_owner="Owner", created_by=self.officer, updated_by=self.officer,
            )
            RiskRegister.objects.filter(pk=risk.pk).update(risk_code=f"A/{source}/003/001")
            risks.append(risk)
        RiskCodeSequence.objects.filter(prefix="A/MRI/003").delete()

        use_division_in_strategic_codes(apps, SimpleNamespace(connection=connection))
        self.assertEqual(
            list(RiskRegister.objects.filter(pk__in=[risk.pk for risk in risks]).order_by("created_at", "pk")
                 .values_list("risk_code", flat=True)),
            ["A/MRI/003/001", "A/MRI/003/002"],
        )
        self.assertEqual(RiskCodeSequence.objects.get(prefix="A/MRI/003").last_number, 2)

    def test_sop_fields_are_required_and_validate_source_and_project(self):
        from .forms import RiskRegisterForm

        base = {"division": self.division_a.pk, "title": "Risiko baru", "cause": "Sebab", "impact": "Dampak"}
        missing = RiskRegisterForm(base, user=self.officer)
        self.assertFalse(missing.is_valid())
        self.assertIn("risk_kind", missing.errors)
        self.assertIn("code_category", missing.errors)

        strategic = RiskRegisterForm({**base, "risk_kind": "A", "code_category": "006"}, user=self.officer)
        self.assertFalse(strategic.is_valid())
        self.assertIn("risk_source", strategic.errors)

        project = RiskRegisterForm({**base, "risk_kind": "C", "code_category": "010"}, user=self.officer)
        self.assertFalse(project.is_valid())
        self.assertIn("division", project.errors)

    def test_operational_source_is_saved_and_restored_on_edit(self):
        self.client.force_login(self.officer)
        payload = self._risk_with_treatments_payload([])
        payload["risk_source"] = "01"
        response = self.client.post(reverse("risk:risk_create"), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        risk = RiskRegister.objects.get(title="Risiko dengan perlakuan")
        self.assertEqual(risk.risk_source, "01")
        self.assertTrue(risk.risk_code.startswith("B/A/"))

        edit_url = reverse("risk:risk_edit", args=[risk.pk])
        edit_page = self.client.get(edit_url, HTTP_HOST="risk.localhost")
        self.assertEqual(edit_page.context["form"]["risk_source"].value(), "01")
        payload["risk_source"] = "02"
        response = self.client.post(edit_url, payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        risk.refresh_from_db()
        self.assertEqual(risk.risk_source, "02")
        self.assertTrue(risk.risk_code.startswith("B/A/"))
        edit_page = self.client.get(edit_url, HTTP_HOST="risk.localhost")
        self.assertEqual(edit_page.context["form"]["risk_source"].value(), "02")
        detail = self.client.get(reverse("risk:risk_detail", args=[risk.pk]), HTTP_HOST="risk.localhost")
        self.assertContains(detail, "Sumber Risiko")
        self.assertContains(detail, "02 - Selain divisi atau proyek")

    def test_criteria_shows_map_and_color_legend_before_likelihoods(self):
        from .criteria import IMPACT_HEADERS, impact_criteria
        from .exports import TEMPLATE
        self.client.force_login(self.head)
        response = self.client.get(reverse("risk:criteria"), HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kriteria Risiko")
        self.assertContains(response, "Kriteria Dampak")
        content = response.content.decode()
        self.assertLess(content.index("<h2>Peta Risiko</h2>"), content.index("<h2>Level Risiko</h2>"))
        self.assertLess(content.index("<h2>Level Risiko</h2>"), content.index("<h2>Kriteria Kemungkinan</h2>"))
        self.assertLess(content.index("<h2>Kriteria Kemungkinan</h2>"), content.index("<h2>Kriteria Dampak</h2>"))
        for heading in IMPACT_HEADERS:
            self.assertContains(response, heading)
        self.assertEqual(response.context["impact_criteria"], impact_criteria())
        self.assertContains(response, "Meninggal dunia, cacat total")
        self.assertEqual(response.context["risk_levels"], [
            ("Sangat Tinggi", "Merah", "red"), ("Tinggi", "Coklat", "orange"),
            ("Sedang", "Kuning", "yellow"), ("Rendah", "Hijau", "green"),
            ("Sangat Rendah", "Biru", "blue"),
        ])
        self.assertContains(response, 'aria-label="Level risiko dan warna"')
        workbook = load_workbook(TEMPLATE, read_only=True, data_only=True)
        try:
            original = list(workbook["NEW Kriteria Dampak"].iter_rows(min_row=8, max_row=12, min_col=1, max_col=9, values_only=True))
            self.assertEqual([(row["level"], *row["criteria"]) for row in impact_criteria()], original)
        finally:
            workbook.close()
        self.assertEqual(self.client.get(reverse("risk:scoring_guide"), HTTP_HOST="risk.localhost").status_code, 200)

    def test_treatment_create_edit_audit_and_export(self):
        self.client.force_login(self.officer)
        payload = {"risk": self.risk.pk, "option": "Mengurangi risiko", "action_plan": "Sosialisasi risiko",
                   "expected_likelihood": 2, "expected_impact": 2, "target_date": "2026-12-31",
                   "responsible_person": "Risk Owner", "notes": "Catatan perlakuan"}
        response = self.client.post(reverse("risk:treatment_create"), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        treatment = RiskTreatment.objects.get(risk=self.risk)
        self.assertEqual(treatment.expected_score, 4)
        self.assertEqual(treatment.expected_level, "Rendah")
        self.assertEqual(treatment.created_by, self.officer)
        self.assertTrue(ActivityLog.objects.filter(action="RISK_TREATMENT_CREATED", target_id=str(treatment.pk)).exists())
        payload.update(action_plan="Sosialisasi diperbarui", expected_impact=3)
        response = self.client.post(reverse("risk:treatment_edit", args=[treatment.pk]), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        treatment.refresh_from_db()
        self.assertEqual(treatment.expected_score, 6)
        self.assertEqual(treatment.action_plan, payload["action_plan"])
        self.assertTrue(ActivityLog.objects.filter(action="RISK_TREATMENT_UPDATED").exists())
        response = self._annual_download()
        exported = load_workbook(BytesIO(b"".join(response.streaming_content)), data_only=True)
        self.assertEqual(exported["Perlakuan Risiko"]["D10"].value, payload["action_plan"])
        self.assertEqual(exported["Perlakuan Risiko"]["G10"].value, 6)
        self.assertEqual(exported["Perlakuan Risiko"]["K10"].value, payload["notes"])
        exported.close()

    def test_detail_adds_treatment_in_table(self):
        self.client.force_login(self.officer)
        url = reverse("risk:risk_detail", args=[self.risk.pk])
        page = self.client.get(url, HTTP_HOST="risk.localhost")
        self.assertContains(page, "Risk Register")
        self.assertContains(page, 'data-add-treatment')
        self.assertContains(page, 'id="new-treatment-row"')
        response = self.client.post(url, {
            "save_treatment": "1", "risk": "999999", "option": "Mengurangi risiko",
            "action_plan": "Tindakan baru", "expected_likelihood": "2", "expected_impact": "2",
        }, HTTP_HOST="risk.localhost")
        self.assertRedirects(response, f"{url}#perlakuan-risiko", fetch_redirect_response=False)
        self.assertEqual(RiskTreatment.objects.get().risk, self.risk)
        invalid = self.client.post(url, {
            "save_treatment": "1", "action_plan": "Tidak lengkap", "expected_likelihood": "2",
        }, HTTP_HOST="risk.localhost")
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, 'id="new-treatment-row"')
        self.assertTrue(invalid.context["treatment_form"].errors)
        self.client.force_login(self.head)
        self.assertNotContains(self.client.get(url, HTTP_HOST="risk.localhost"), 'data-add-treatment')
        self.assertEqual(self.client.post(url, {"save_treatment": "1", "action_plan": "Ditolak"},
                                          HTTP_HOST="risk.localhost").status_code, 403)

    def test_treatment_permissions_and_validation(self):
        other = RiskRegister.objects.create(division=self.division_b, title="Risiko privat", category="operational",
                                            inherent_likelihood=1, inherent_impact=1, residual_likelihood=1,
                                            residual_impact=1, created_by=self.officer, updated_by=self.officer)
        treatment = RiskTreatment.objects.create(risk=other, action_plan="Aksi privat", created_by=self.officer, updated_by=self.officer)
        self.client.force_login(self.officer)
        response = self.client.get(reverse("risk:treatment_list"), HTTP_HOST="risk.localhost")
        self.assertContains(response, self.risk.title)
        self.assertNotContains(response, other.title)
        self.assertEqual(self.client.get(reverse("risk:treatment_edit", args=[treatment.pk]), HTTP_HOST="risk.localhost").status_code, 404)
        for data in ({"risk": other.pk, "action_plan": "Forged"},
                     {"risk": self.risk.pk, "action_plan": "Invalid", "expected_likelihood": 6, "expected_impact": 2},
                     {"risk": self.risk.pk, "action_plan": "Incomplete", "expected_likelihood": 2}):
            response = self.client.post(reverse("risk:treatment_create"), data, HTTP_HOST="risk.localhost")
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(RiskTreatment.objects.count(), 1)
        self.client.force_login(self.head)
        self.assertNotContains(self.client.get(reverse("risk:treatment_list"), HTTP_HOST="risk.localhost"), "+ Tambah Perlakuan")
        self.assertEqual(self.client.post(reverse("risk:treatment_create"), {"risk": self.risk.pk}, HTTP_HOST="risk.localhost").status_code, 403)

    def test_manager_can_edit_treatments_across_divisions(self):
        manager = get_user_model().objects.create_user(username="treatment-manager", role="risk")
        RiskAccess.objects.create(user=manager, role="manager_member")
        self.client.force_login(manager)
        response = self.client.post(reverse("risk:treatment_create"), {"risk": self.risk.pk, "action_plan": "Rencana manajemen"}, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        treatment = RiskTreatment.objects.get(risk=self.risk)
        self.assertEqual(self.client.get(reverse("risk:treatment_edit", args=[treatment.pk]), HTTP_HOST="risk.localhost").status_code, 200)

    def test_managers_can_replace_division_pic_and_audit_access_changes(self):
        User = get_user_model()
        replacement = User.objects.create_user(username="new-pic", password="test-pass-123", role="risk")
        other_access = RiskAccess.objects.create(user=self.officer, role="risk_officer", division=self.division_b)
        for role in ("head_manager", "manager_member"):
            manager = User.objects.create_user(username=role, password="test-pass-123", role="risk")
            manager_access = RiskAccess.objects.create(user=manager, role=role)
            self.client.force_login(manager)
            listing = self.client.get(reverse("risk:divisions"), HTTP_HOST="risk.localhost")
            self.assertContains(listing, "Atur PIC")
            url = reverse("risk:division_pic_edit", args=[self.division_a.pk])
            self.assertEqual(self.client.get(url, HTTP_HOST="risk.localhost").status_code, 200)
            response = self.client.post(url, {"risk_officer": replacement.pk, "risk_owner": self.head.pk}, HTTP_HOST="risk.localhost")
            self.assertRedirects(response, reverse("risk:divisions"), fetch_redirect_response=False)
            self.assertTrue(RiskAccess.objects.filter(user=replacement, division=self.division_a, role="risk_officer", is_active=True).exists())
            self.assertFalse(RiskAccess.objects.get(user=self.officer, division=self.division_a, role="risk_officer").is_active)
            other_access.refresh_from_db()
            manager_access.refresh_from_db()
            self.assertTrue(other_access.is_active)
            self.assertTrue(manager_access.is_active)
            self.risk.refresh_from_db()
            self.assertEqual(self.risk.risk_owner, self.head.get_full_name() or self.head.username)
            self.assertEqual(self.risk.risk_officer, replacement.get_full_name() or replacement.username)
        self.assertEqual(ActivityLog.objects.filter(action="DIVISION_PIC_UPDATED").count(), 1)
        log = ActivityLog.objects.get(action="DIVISION_PIC_UPDATED")
        self.assertEqual(log.metadata["before"]["risk_officer"], [self.officer.pk])
        self.assertEqual(log.metadata["after"]["risk_officer"], [replacement.pk])
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(reverse("risk:risk_detail", args=[self.risk.pk]), HTTP_HOST="risk.localhost").status_code, 404)
        self.client.force_login(replacement)
        self.assertEqual(self.client.get(reverse("risk:risk_edit", args=[self.risk.pk]), HTTP_HOST="risk.localhost").status_code, 200)

    def test_pic_edit_rejects_non_managers_and_inactive_users(self):
        url = reverse("risk:division_pic_edit", args=[self.division_a.pk])
        self.client.force_login(self.head)
        self.assertNotContains(self.client.get(reverse("risk:divisions"), HTTP_HOST="risk.localhost"), "Atur PIC")
        self.assertEqual(self.client.get(url, HTTP_HOST="risk.localhost").status_code, 403)
        self.assertEqual(self.client.post(url, {}, HTTP_HOST="risk.localhost").status_code, 403)
        self.client.force_login(self.officer)
        self.assertContains(self.client.get(reverse("risk:divisions"), HTTP_HOST="risk.localhost"), "Atur PIC")
        self.assertEqual(self.client.get(url, HTTP_HOST="risk.localhost").status_code, 200)
        self.assertEqual(self.client.post(url, {"risk_officer": self.officer.pk, "risk_owner": self.head.pk}, HTTP_HOST="risk.localhost").status_code, 302)
        other_url = reverse("risk:division_pic_edit", args=[self.division_b.pk])
        self.assertEqual(self.client.get(other_url, HTTP_HOST="risk.localhost").status_code, 403)
        self.assertEqual(self.client.post(other_url, {"risk_officer": self.officer.pk, "risk_owner": self.head.pk}, HTTP_HOST="risk.localhost").status_code, 403)
        admin = get_user_model().objects.create_superuser(username="pic-admin", password="test-pass-123")
        inactive = get_user_model().objects.create_user(username="inactive-pic", is_active=False, role="risk")
        self.client.force_login(admin)
        response = self.client.post(url, {"risk_officer": inactive.pk, "risk_owner": self.head.pk}, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertTrue(RiskAccess.objects.get(user=self.officer, division=self.division_a, role="risk_officer").is_active)
        self.assertFalse(ActivityLog.objects.filter(action="DIVISION_PIC_UPDATED").exists())
        response = self.client.post(url, {}, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertTrue(RiskAccess.objects.filter(division=self.division_a, is_active=True).exists())
        self.client.post(url, {"risk_officer": self.officer.pk, "risk_owner": self.head.pk}, HTTP_HOST="risk.localhost")
        self.assertEqual(RiskAccess.objects.filter(user=self.officer, division=self.division_a, role="risk_officer").count(), 1)
        self.assertTrue(RiskAccess.objects.get(user=self.officer, division=self.division_a, role="risk_officer").is_active)

    def test_division_pic_shows_names_and_missing_assignments(self):
        manager = get_user_model().objects.create_user(username="pic-manager", role="risk")
        RiskAccess.objects.create(user=manager, role="manager_member")
        self.head.first_name, self.head.last_name = "Nama", "Owner"
        self.head.save(update_fields=["first_name", "last_name"])
        self.officer.first_name, self.officer.last_name = "Nama", "Officer"
        self.officer.save(update_fields=["first_name", "last_name"])
        self.client.force_login(manager)
        page = self.client.get(reverse("risk:divisions"), HTTP_HOST="risk.localhost")
        self.assertContains(page, "Nama Owner")
        self.assertContains(page, "Nama Officer")
        self.assertContains(page, "Belum ditetapkan")
        editor = self.client.get(reverse("risk:division_pic_edit", args=[self.division_a.pk]), HTTP_HOST="risk.localhost")
        self.assertContains(editor, f'<option value="{self.head.pk}" selected>Nama Owner</option>', html=True)
        self.assertNotContains(editor, "Nama Owner (risk)")

    def test_legal_umum_pic_has_separate_it_hrd_and_humas_staff(self):
        User = get_user_model()
        legal = RiskDivision.objects.get(code="LUM")
        manager = User.objects.create_user(username="legal-manager", role="risk")
        RiskAccess.objects.create(user=manager, role="manager_member")
        staff = {
            role: User.objects.create_user(username=f"legal-{role}", first_name=label, role="risk")
            for role, label in (("staff_it", "Teknologi"), ("staff_hrd", "Personalia"),
                                ("staff_humas", "Hubungan Masyarakat"))
        }
        self.client.force_login(manager)
        url = reverse("risk:division_pic_edit", args=[legal.pk])
        page = self.client.get(url, HTTP_HOST="risk.localhost")
        for role, label in (("staff_it", "Staff IT"), ("staff_hrd", "HRD"),
                            ("staff_humas", "Humas")):
            self.assertContains(page, f'name="{role}"')
            self.assertContains(page, label)
        self.assertNotContains(self.client.get(reverse("risk:division_pic_edit", args=[self.division_a.pk]),
                                              HTTP_HOST="risk.localhost"), 'name="staff_it"')
        payload = {"risk_officer": self.officer.pk, "risk_owner": self.head.pk,
                   **{role: user.pk for role, user in staff.items()}}
        self.assertEqual(self.client.post(url, payload, HTTP_HOST="risk.localhost").status_code, 302)
        for role, user in staff.items():
            self.assertTrue(RiskAccess.objects.filter(division=legal, role=role, user=user,
                                                      is_active=True).exists())
        listing = self.client.get(reverse("risk:divisions"), HTTP_HOST="risk.localhost")
        for name in ("Teknologi", "Personalia", "Hubungan Masyarakat"):
            self.assertContains(listing, name)
        payload.pop("staff_humas")
        self.assertEqual(self.client.post(url, payload, HTTP_HOST="risk.localhost").status_code, 302)
        self.assertFalse(RiskAccess.objects.get(division=legal, role="staff_humas", user=staff["staff_humas"]).is_active)

    def test_risk_officer_can_assign_pic_only_for_own_division(self):
        replacement = get_user_model().objects.create_user(
            username="replacement-officer", first_name="Petugas", last_name="Baru", role="risk",
        )
        self.client.force_login(self.officer)
        response = self.client.post(
            reverse("risk:division_pic_edit", args=[self.division_a.pk]),
            {"risk_officer": replacement.pk, "risk_owner": self.head.pk},
            HTTP_HOST="risk.localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(RiskAccess.objects.filter(
            user=replacement, division=self.division_a, role="risk_officer", is_active=True,
        ).exists())
        self.risk.refresh_from_db()
        self.assertEqual(self.risk.risk_officer, "Petugas Baru")
        self.assertEqual(self.client.get(reverse("risk:division_pic_edit", args=[self.division_b.pk]), HTTP_HOST="risk.localhost").status_code, 403)

    def test_new_risk_requires_both_division_pic_names(self):
        manager = get_user_model().objects.create_user(username="risk-manager-pic", role="risk")
        RiskAccess.objects.create(user=manager, role="manager_member")
        self.client.force_login(manager)
        data = {
            "division": self.division_b.pk, "title": "Risiko tanpa PIC",
            "cause": "Sebab", "impact": "Dampak", "inherent_likelihood": 1,
            "inherent_impact": 5, "residual_likelihood": 1, "residual_impact": 5,
            "risk_owner": "Nama palsu", "risk_officer": "Nama palsu",
        }
        response = self.client.post(reverse("risk:risk_create"), data, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertIn("division", response.context["form"].errors)
        self.assertFalse(RiskRegister.objects.filter(title="Risiko tanpa PIC").exists())

    def test_document_form_creates_risk_without_extra_fields(self):
        self.client.force_login(self.officer)
        payload = {
            "division": self.division_a.pk, "title": "Risiko sesuai dokumen",
            "risk_kind": "B", "code_category": "010",
            "strategic_objective": "Sasaran", "indication": "Indikasi",
            "cause": "Sebab", "controllability": "controllable", "impact": "Dampak",
            "inherent_likelihood": 4, "inherent_impact": 4,
            "existing_controls": "Kontrol", "control_effectiveness": "adequate",
            "residual_likelihood": 2, "residual_impact": 3, "is_priority": "on",
            "risk_owner": "Pemilik", "risk_officer": "Officer",
            "identification_notes": "Catatan identifikasi", "evaluation_notes": "Catatan evaluasi",
        }
        response = self.client.post(reverse("risk:risk_create"), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        risk = RiskRegister.objects.get(title=payload["title"])
        self.assertEqual(risk.identification_notes, payload["identification_notes"])
        self.assertEqual(risk.evaluation_notes, payload["evaluation_notes"])
        self.assertEqual(risk.description, payload["indication"])
        self.assertEqual(risk.status, "open")
        self.assertEqual(risk.risk_owner, self.head.username)
        self.assertEqual(risk.risk_officer, self.officer.username)

        risk.category = "financial"
        risk.status = "closed"
        risk.mitigation_plan = "Mitigasi sebelumnya"
        risk.description = "Uraian sebelumnya"
        risk.save()
        payload["indication"] = "Indikasi diperbarui"
        response = self.client.post(reverse("risk:risk_edit", args=[risk.pk]), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        risk.refresh_from_db()
        self.assertEqual(risk.category, "financial")
        self.assertEqual(risk.status, "closed")
        self.assertEqual(risk.mitigation_plan, "Mitigasi sebelumnya")
        self.assertEqual(risk.description, "Uraian sebelumnya")
        self.assertEqual(risk.indication, "Indikasi diperbarui")

    def test_document_form_only_renders_document_fields(self):
        self.client.force_login(self.officer)
        response = self.client.get(reverse("risk:risk_create"), HTTP_HOST="risk.localhost")
        self.assertContains(response, "Analisis &amp; Evaluasi Risiko")
        self.assertContains(response, "Risiko Inheren (risiko sebelum pengendalian)")
        self.assertContains(response, "Risiko Setelah Pengendalian yang Ada")
        self.assertContains(response, "Simpan Risiko", count=1)
        self.assertNotContains(response, "Simpan Identifikasi Risiko")
        for name in ("risk_kind", "risk_source", "code_category"):
            self.assertContains(response, f'name="{name}"')
        for name in ("category", "description", "status", "mitigation_plan", "target_date"):
            self.assertNotContains(response, f'name="{name}"')
        self.assertContains(response, 'name="control_effectiveness"', count=3)
        self.assertContains(response, "+ Tambah Pengendalian")
        self.assertNotContains(response, "+ Tambah Nama Risiko")
        self.assertContains(response, 'name="controls-TOTAL_FORMS"')
        self.assertContains(response, 'id="residualScore"')
        self.assertContains(response, '>Skor Risiko</th>', count=2)
        for field in ("inherent_likelihood", "inherent_impact", "residual_likelihood", "residual_impact"):
            self.assertContains(response, f'name="{field}"')
            self.assertContains(response, f'id="id_{field}"')

    def test_likelihood_and_impact_inputs_reject_values_over_five(self):
        from .forms import RiskRegisterForm

        form = RiskRegisterForm({
            "division": self.division_a.pk, "risk_kind": "B", "code_category": "010",
            "title": "Risiko skor terlalu tinggi", "cause": "Sebab", "impact": "Dampak",
            "inherent_likelihood": 5, "inherent_impact": 6,
            "residual_likelihood": 6, "residual_impact": 5,
        }, user=self.officer)
        self.assertFalse(form.is_valid())
        self.assertIn("inherent_impact", form.errors)
        self.assertIn("residual_likelihood", form.errors)
        for name in ("inherent_likelihood", "inherent_impact", "residual_likelihood", "residual_impact"):
            self.assertEqual(form.fields[name].widget.attrs["max"], 5)

    def test_single_save_button_accepts_identification_without_analysis(self):
        self.client.force_login(self.officer)
        response = self.client.post(reverse("risk:risk_create"), {
            "division": self.division_a.pk, "risk_kind": "B", "code_category": "010",
            "title": "Risiko identifikasi saja", "cause": "Sebab risiko", "impact": "Dampak risiko",
        }, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        risk = RiskRegister.objects.get(title="Risiko identifikasi saja")
        self.assertIsNone(risk.residual_likelihood)
        self.assertIsNone(risk.residual_impact)
        self.assertFalse(risk.treatments.exists())

    def test_additional_controls_follow_their_risk_and_survive_identification_save(self):
        self.client.force_login(self.officer)
        payload = self._risk_with_treatments_payload([])
        payload.update({
            "additional-TOTAL_FORMS": 1, "additional-INITIAL_FORMS": 0,
            "additional-MIN_NUM_FORMS": 0, "additional-MAX_NUM_FORMS": 99,
            "additional-0-division": self.division_a.pk,
            "additional-0-risk_kind": "B", "additional-0-code_category": "010",
            "additional-0-title": "Risiko kedua dengan pengendalian",
            "additional-0-cause": "Sebab kedua", "additional-0-impact": "Dampak kedua",
            "controls-TOTAL_FORMS": 2, "controls-INITIAL_FORMS": 0,
            "controls-MIN_NUM_FORMS": 0, "controls-MAX_NUM_FORMS": 99,
            "controls-0-risk_index": 0, "controls-0-description": "Kontrol tambahan pertama",
            "controls-0-effectiveness": "effective", "controls-0-notes": "Catatan pertama",
            "controls-1-risk_index": 1, "controls-1-description": "Kontrol risiko kedua",
            "controls-1-effectiveness": "adequate", "controls-1-notes": "Catatan kedua",
        })
        response = self.client.post(reverse("risk:risk_create"), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        first = RiskRegister.objects.get(title="Risiko dengan perlakuan")
        second = RiskRegister.objects.get(title="Risiko kedua dengan pengendalian")
        self.assertEqual(list(first.additional_controls.values_list("position", "description", "effectiveness", "notes")), [
            (2, "Kontrol tambahan pertama", "effective", "Catatan pertama"),
        ])
        self.assertEqual(list(second.additional_controls.values_list("position", "description")), [(2, "Kontrol risiko kedua")])

        edit = self.client.get(reverse("risk:risk_edit", args=[first.pk]), HTTP_HOST="risk.localhost")
        self.assertContains(edit, "Kontrol tambahan pertama")
        control_row = edit.content.decode().split('data-control-row>', 1)[1].split('</tr>', 1)[0]
        self.assertEqual(control_row.count('<td'), 5)
        self.assertNotIn('data-control-level', control_row)
        self.assertNotIn('data-control-score', control_row)
        self.assertContains(self.client.get(reverse("risk:risk_detail", args=[first.pk]), HTTP_HOST="risk.localhost"), "Catatan pertama")
        identification = self._risk_with_treatments_payload([])
        identification["save_scope"] = "identification"
        response = self.client.post(reverse("risk:risk_edit", args=[first.pk]), identification, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(first.additional_controls.count(), 1)

    def test_additional_controls_can_be_changed_and_deleted_on_edit(self):
        RiskControl.objects.create(risk=self.risk, position=2, description="Kontrol lama", effectiveness="adequate")
        self.client.force_login(self.officer)
        payload = self._risk_with_treatments_payload([])
        payload.update({
            "controls-TOTAL_FORMS": 2, "controls-INITIAL_FORMS": 1,
            "controls-MIN_NUM_FORMS": 0, "controls-MAX_NUM_FORMS": 99,
            "controls-0-risk_index": 0, "controls-0-description": "Kontrol lama",
            "controls-0-effectiveness": "adequate", "controls-0-DELETE": "on",
            "controls-1-risk_index": 0, "controls-1-description": "Kontrol baru",
            "controls-1-effectiveness": "ineffective", "controls-1-notes": "Perlu perbaikan",
        })
        response = self.client.post(reverse("risk:risk_edit", args=[self.risk.pk]), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(self.risk.additional_controls.values_list("position", "description", "effectiveness", "notes")), [
            (2, "Kontrol baru", "ineffective", "Perlu perbaikan"),
        ])

    def test_invalid_control_target_does_not_create_risk(self):
        self.client.force_login(self.officer)
        payload = self._risk_with_treatments_payload([])
        payload.update({
            "controls-TOTAL_FORMS": 1, "controls-INITIAL_FORMS": 0,
            "controls-MIN_NUM_FORMS": 0, "controls-MAX_NUM_FORMS": 99,
            "controls-0-risk_index": 1, "controls-0-description": "Kontrol tanpa risiko",
        })
        response = self.client.post(reverse("risk:risk_create"), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["control_formset"].forms[0].errors)
        self.assertFalse(RiskRegister.objects.filter(title="Risiko dengan perlakuan").exists())

    def test_deleted_additional_risk_is_not_saved_and_later_risk_keeps_its_index(self):
        self.client.force_login(self.officer)
        payload = self._risk_with_treatments_payload([])
        payload.update({
            "additional-TOTAL_FORMS": 2, "additional-INITIAL_FORMS": 0,
            "additional-MIN_NUM_FORMS": 0, "additional-MAX_NUM_FORMS": 99,
            "additional-0-title": "Risiko yang dihapus", "additional-0-DELETE": "on",
            "additional-1-division": self.division_a.pk,
            "additional-1-risk_kind": "B", "additional-1-code_category": "010",
            "additional-1-title": "Risiko yang tetap", "additional-1-cause": "Sebab",
            "additional-1-impact": "Dampak",
            "controls-TOTAL_FORMS": 1, "controls-INITIAL_FORMS": 0,
            "controls-MIN_NUM_FORMS": 0, "controls-MAX_NUM_FORMS": 99,
            "controls-0-risk_index": 2, "controls-0-description": "Kontrol risiko tetap",
        })
        response = self.client.post(reverse("risk:risk_create"), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(RiskRegister.objects.filter(title="Risiko yang dihapus").exists())
        remaining = RiskRegister.objects.get(title="Risiko yang tetap")
        self.assertEqual(list(remaining.additional_controls.values_list("description", flat=True)), ["Kontrol risiko tetap"])

    def test_deleted_risk_cannot_receive_new_control(self):
        self.client.force_login(self.officer)
        payload = self._risk_with_treatments_payload([])
        payload.update({
            "additional-TOTAL_FORMS": 1, "additional-INITIAL_FORMS": 0,
            "additional-MIN_NUM_FORMS": 0, "additional-MAX_NUM_FORMS": 99,
            "additional-0-title": "Risiko yang dihapus", "additional-0-DELETE": "on",
            "controls-TOTAL_FORMS": 1, "controls-INITIAL_FORMS": 0,
            "controls-MIN_NUM_FORMS": 0, "controls-MAX_NUM_FORMS": 99,
            "controls-0-risk_index": 1, "controls-0-description": "Kontrol tanpa risiko",
        })
        response = self.client.post(reverse("risk:risk_create"), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["control_formset"].forms[0].errors)
        self.assertFalse(RiskRegister.objects.filter(title="Risiko dengan perlakuan").exists())

    def test_identification_can_be_saved_before_scoring_analysis_and_treatment(self):
        self.client.force_login(self.officer)
        payload = {
            "save_scope": "identification", "division": self.division_a.pk,
            "risk_kind": "B", "code_category": "010",
            "title": "Risiko pertama", "cause": "Sebab pertama", "impact": "Dampak pertama",
            "residual_likelihood": 99,
            "additional-TOTAL_FORMS": 1, "additional-INITIAL_FORMS": 0,
            "additional-MIN_NUM_FORMS": 0, "additional-MAX_NUM_FORMS": 99,
            "additional-0-division": self.division_a.pk,
            "additional-0-risk_kind": "B", "additional-0-code_category": "010",
            "additional-0-title": "Risiko kedua", "additional-0-cause": "Sebab kedua",
            "additional-0-impact": "Dampak kedua", "additional-0-residual_likelihood": 99,
            "treatments-TOTAL_FORMS": 1, "treatments-INITIAL_FORMS": 0,
            "treatments-MIN_NUM_FORMS": 0, "treatments-MAX_NUM_FORMS": 100,
            "treatments-0-action_plan": "Belum disimpan",
        }
        response = self.client.post(reverse("risk:risk_create"), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        risks = list(RiskRegister.objects.filter(title__in=["Risiko pertama", "Risiko kedua"]).order_by("title"))
        self.assertEqual(len(risks), 2)
        for risk in risks:
            self.assertIsNone(risk.inherent_likelihood)
            self.assertIsNone(risk.inherent_impact)
            self.assertIsNone(risk.residual_likelihood)
            self.assertIsNone(risk.residual_impact)
            self.assertIsNone(risk.inherent_score)
            self.assertIsNone(risk.residual_score)
            self.assertEqual(risk.inherent_level, "-")
            self.assertEqual(risk.risk_level, "-")
            self.assertFalse(risk.treatments.exists())
        first = risks[1] if risks[1].title == "Risiko pertama" else risks[0]
        self.assertEqual(self.client.get(reverse("risk:risk_detail", args=[first.pk]),
                                         HTTP_HOST="risk.localhost").status_code, 200)

        analysis = {
            "division": self.division_a.pk, "title": first.title,
            "risk_kind": "B", "code_category": "010",
            "cause": first.cause, "impact": first.impact,
            "inherent_likelihood": 2, "inherent_impact": 3,
            "residual_likelihood": 1, "residual_impact": 2,
            "existing_controls": "Kontrol", "control_effectiveness": "adequate",
        }
        response = self.client.post(reverse("risk:risk_edit", args=[first.pk]), analysis,
                                    HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        RiskTreatment.objects.create(risk=first, action_plan="Rencana tetap",
                                     created_by=self.officer, updated_by=self.officer)
        response = self.client.post(reverse("risk:risk_edit", args=[first.pk]), {
            **analysis, "save_scope": "identification", "title": "Risiko pertama diperbarui",
            "residual_likelihood": 5, "residual_impact": 5, "existing_controls": "Terhapus?",
        }, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        first.refresh_from_db()
        self.assertEqual(first.title, "Risiko pertama diperbarui")
        self.assertEqual((first.residual_likelihood, first.residual_impact), (1, 2))
        self.assertEqual(first.existing_controls, "Kontrol")
        self.assertEqual(list(first.treatments.values_list("action_plan", flat=True)), ["Rencana tetap"])

    def test_multiple_causes_stay_with_one_risk_and_can_be_edited(self):
        self.client.force_login(self.officer)
        payload = {
            "division": self.division_a.pk, "title": "Risiko dengan beberapa sebab",
            "risk_kind": "B", "code_category": "010",
            "cause": "Sebab pertama", "controllability": "controllable",
            "impact": "Dampak", "inherent_likelihood": 2, "inherent_impact": 3,
            "residual_likelihood": 2, "residual_impact": 2,
            "causes-TOTAL_FORMS": 2, "causes-INITIAL_FORMS": 0,
            "causes-MIN_NUM_FORMS": 0, "causes-MAX_NUM_FORMS": 99,
            "causes-0-risk_index": 0, "causes-0-description": "Sebab kedua",
            "causes-0-controllability": "uncontrollable",
            "causes-0-impact": "Dampak kedua", "causes-0-inherent_likelihood": 4,
            "causes-0-inherent_impact": 3, "causes-0-identification_notes": "Catatan kedua",
            "causes-1-risk_index": 0, "causes-1-description": "Sebab ketiga",
            "causes-1-controllability": "controllable",
            "causes-1-impact": "Dampak ketiga", "causes-1-inherent_likelihood": 2,
            "causes-1-inherent_impact": 5, "causes-1-identification_notes": "Catatan ketiga",
        }
        response = self.client.post(reverse("risk:risk_create"), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        risk = RiskRegister.objects.get(title=payload["title"])
        self.assertEqual(RiskRegister.objects.filter(title=payload["title"]).count(), 1)
        self.assertEqual(list(risk.additional_causes.values_list("position", "description", "controllability")), [
            (2, "Sebab kedua", "uncontrollable"), (3, "Sebab ketiga", "controllable"),
        ])
        self.assertEqual(list(risk.additional_causes.values_list(
            "impact", "inherent_likelihood", "inherent_impact", "identification_notes"
        )), [("Dampak kedua", 4, 3, "Catatan kedua"), ("Dampak ketiga", 2, 5, "Catatan ketiga")])
        from .exports import annual_risk_workbook
        workbook = load_workbook(annual_risk_workbook(
            [risk], division=self.division_a, year=risk.created_at.year,
        ), data_only=True)
        sheet = workbook["Identifikasi Risiko"]
        self.assertEqual([sheet[f"{column}11"].value for column in ("F", "H", "I", "J", "M")],
                         ["Sebab kedua", "Dampak kedua", None, None, "Catatan kedua"])
        self.assertEqual([sheet[f"{column}10"].value for column in ("I", "J")], [2, 3])
        response = self.client.get(reverse("risk:risk_edit", args=[risk.pk]), HTTP_HOST="risk.localhost")
        self.assertContains(response, "Sebab kedua")
        self.assertContains(response, "Sebab ketiga")
        self.assertContains(response, '<tr data-cause-row>', count=3)
        cause_row_markup = response.content.decode().split('<tr data-cause-row>', 1)[1].split('</tr>', 1)[0]
        self.assertNotIn('colspan="5"', cause_row_markup)
        self.assertNotIn('data-cause-risk-label', cause_row_markup)
        self.assertNotIn('data-cause-level', cause_row_markup)
        self.assertEqual(cause_row_markup.count('<td'), 4)
        self.assertTrue(response.context["cause_formset"].forms[0].fields["inherent_likelihood"].widget.is_hidden)
        detail = self.client.get(reverse("risk:risk_detail", args=[risk.pk]), HTTP_HOST="risk.localhost")
        self.assertContains(detail, 'rowspan="3"', count=4)
        self.assertContains(detail, "Skor Risiko")
        self.assertContains(detail, ">6</td>")
        self.assertContains(response, 'name="causes-0-impact"')
        self.assertContains(response, 'name="causes-0-inherent_likelihood"')
        self.assertContains(response, 'name="causes-0-inherent_impact"')
        self.assertContains(response, 'name="causes-0-identification_notes"')
        payload.update({"causes-INITIAL_FORMS": 2, "causes-0-DELETE": "on"})
        response = self.client.post(reverse("risk:risk_edit", args=[risk.pk]), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(risk.additional_causes.values_list("position", "description")), [(2, "Sebab ketiga")])
        self.assertEqual(risk.additional_causes.get().impact, "Dampak ketiga")

    def test_multi_risk_form_places_metadata_and_selectors_in_their_table_columns(self):
        self.client.force_login(self.officer)
        response = self.client.get(reverse("risk:risk_create"), HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        identification = html.split('id="identifikasi"', 1)[1].split('id="analisis"', 1)[0]
        self.assertIn('>Nama Divisi</th>', identification)
        self.assertIn('>Skor Risiko</th>', identification)
        self.assertIn('id="inherentScore"', identification)
        self.assertEqual(identification.count('data-identification-row="0"'), 1)
        self.assertNotIn('id="addRiskRow"', identification)
        self.assertNotIn('>Risk Owner</th>', identification)
        self.assertNotIn('>Risk Officer</th>', identification)
        self.assertLess(identification.index('name="division"'), identification.index('name="title"'))
        self.assertNotIn('name="risk_owner"', identification)
        self.assertNotIn('name="risk_officer"', identification)
        self.assertNotIn('class="rw-metadata"', identification)
        analysis = html.split('id="analisis"', 1)[1].split('id="perlakuan"', 1)[0]
        self.assertIn('<td data-evaluation-number>1</td><td><select data-evaluation-risk-select', analysis)
        self.assertIn('data-evaluation-risk-select', analysis)
        self.assertNotIn('data-analysis-risk-title', analysis)
        self.assertNotIn('id="addAnalysisRiskRow"', analysis)
        self.assertEqual(analysis.count('data-evaluation-index="0"'), 1)
        self.assertNotIn('id="emptyEvaluationRow"', analysis)
        self.assertIn('id="residualScore"', analysis)
        treatment = html.split('id="perlakuan"', 1)[1]
        self.assertIn('name="treatments-0-risk_index"', treatment)
        self.assertIn('data-treatment-risk-select', treatment)

    def test_register_summary_respects_division_access_and_current_filters(self):
        for division, title in ((self.division_a, "Prioritas terlihat"), (self.division_b, "Prioritas privat")):
            RiskRegister.objects.create(
                division=division, title=title, category="operational", is_priority=True,
                inherent_likelihood=5, inherent_impact=5, residual_likelihood=4, residual_impact=4,
                status="closed", created_by=self.officer, updated_by=self.officer,
            )
        self.client.force_login(self.officer)
        response = self.client.get(reverse("risk:risk_list"), HTTP_HOST="risk.localhost")
        self.assertEqual(response.context["register_summary"], {"total": 2, "priority": 1, "high": 1, "closed": 1})
        self.assertNotContains(response, "Prioritas privat")
        response = self.client.get(reverse("risk:risk_list"), {"q": "Prioritas terlihat", "status": "closed"}, HTTP_HOST="risk.localhost")
        self.assertEqual(response.context["register_summary"], {"total": 1, "priority": 1, "high": 1, "closed": 1})
        response = self.client.get(reverse("risk:risk_list"), {"q": "Tidak ditemukan"}, HTTP_HOST="risk.localhost")
        self.assertEqual(response.context["register_summary"], {"total": 0, "priority": 0, "high": 0, "closed": 0})

    def test_register_search_is_visible_and_removing_one_filter_keeps_the_rest(self):
        from html.parser import HTMLParser
        from urllib.parse import parse_qs, urlsplit

        class RegisterControls(HTMLParser):
            def __init__(self):
                super().__init__()
                self.in_details = False
                self.visible_search = False
                self.links = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "details":
                    self.in_details = True
                if tag == "input" and attrs.get("type") == "search" and not self.in_details:
                    self.visible_search = True
                if tag == "a" and "rw-filter-chip" in attrs.get("class", "").split():
                    self.links.append(attrs)

            def handle_endtag(self, tag):
                if tag == "details":
                    self.in_details = False

        self.client.force_login(self.officer)
        params = {"q": "operasional", "year": self.risk.created_at.year, "status": "mitigating", "sort": "title", "order": "desc", "page": 2}
        response = self.client.get(reverse("risk:risk_list"), params, HTTP_HOST="risk.localhost")
        controls = RegisterControls()
        controls.feed(response.content.decode())
        self.assertTrue(controls.visible_search)
        year_link = next(link for link in controls.links if link["title"].startswith("Hapus filter Tahun:"))
        remaining = parse_qs(urlsplit(year_link["href"]).query)
        self.assertNotIn("year", remaining)
        self.assertNotIn("page", remaining)
        self.assertEqual(remaining["q"], ["operasional"])
        self.assertEqual(remaining["status"], ["mitigating"])
        self.assertEqual(remaining["sort"], ["title"])
        self.assertEqual(remaining["order"], ["desc"])
        self.assertEqual(len(response.context["active_filters"]), 3)

    def _risk_with_treatments_payload(self, rows, *, initial=0):
        data = {
            "division": self.division_a.pk, "title": "Risiko dengan perlakuan",
            "risk_kind": "B", "code_category": "010",
            "indication": "Indikasi", "cause": "Sebab", "impact": "Dampak",
            "inherent_likelihood": 4, "inherent_impact": 4, "existing_controls": "Kontrol",
            "control_effectiveness": "adequate", "residual_likelihood": 2, "residual_impact": 3,
            "risk_owner": "Pemilik", "risk_officer": "Officer",
            "treatments-TOTAL_FORMS": len(rows), "treatments-INITIAL_FORMS": initial,
            "treatments-MIN_NUM_FORMS": 0, "treatments-MAX_NUM_FORMS": 100,
        }
        for index, row in enumerate(rows):
            data.update({f"treatments-{index}-{field}": value for field, value in row.items()})
        return data

    def test_create_risk_saves_multiple_inline_treatments_and_blank_row(self):
        self.client.force_login(self.officer)
        page = self.client.get(reverse("risk:risk_create"), HTTP_HOST="risk.localhost")
        content = page.content.decode()
        self.assertNotContains(page, "Tambah Baris Risiko")
        self.assertLess(content.index('<h2 class="text-lg font-bold">Analisis &amp; Evaluasi Risiko'),
                        content.index('<h2 class="text-lg font-bold">Perlakuan Risiko'))
        self.assertContains(page, 'name="treatments-TOTAL_FORMS"')
        rows = [
            {"option": "Sosialisasi", "action_plan": "Sosialisasi Produk Manajemen Risiko",
             "expected_likelihood": 2, "expected_impact": 2, "target_date": "2026-12-31",
             "responsible_person": "Risk Owner", "notes": "Catatan"},
            {"option": "Kompetensi", "action_plan": "Mengikuti seminar", "responsible_person": "Divisi MR"},
            {},
        ]
        response = self.client.post(reverse("risk:risk_create"), self._risk_with_treatments_payload(rows), HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        risk = RiskRegister.objects.get(title="Risiko dengan perlakuan")
        self.assertEqual(risk.treatments.count(), 2)
        treatment = risk.treatments.get(option="Sosialisasi")
        self.assertEqual(treatment.expected_score, 4)
        self.assertEqual(treatment.created_by, self.officer)
        self.assertEqual(treatment.notes, "Catatan")
        self.assertEqual(ActivityLog.objects.filter(action="RISK_TREATMENT_CREATED").count(), 2)

    def test_create_multiple_risks_with_treatment_linked_to_selected_identification(self):
        self.client.force_login(self.officer)
        payload = self._risk_with_treatments_payload([
            {"risk_index": 1, "action_plan": "Aksi risiko kedua"},
            {"action_plan": "Aksi risiko pertama"},
        ])
        payload.update({
            "additional-TOTAL_FORMS": 1, "additional-INITIAL_FORMS": 0,
            "additional-MIN_NUM_FORMS": 0, "additional-MAX_NUM_FORMS": 99,
            "additional-0-division": self.division_a.pk,
            "additional-0-risk_kind": "B", "additional-0-code_category": "010",
            "additional-0-title": "Risiko kedua",
            "additional-0-cause": "Sebab kedua",
            "additional-0-impact": "Dampak kedua",
            "additional-0-inherent_likelihood": 3,
            "additional-0-inherent_impact": 4,
            "additional-0-residual_likelihood": 2,
            "additional-0-residual_impact": 2,
            "additional-0-risk_owner": "Pemilik kedua",
        })
        response = self.client.post(reverse("risk:risk_create"), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RiskRegister.objects.filter(title__in=["Risiko dengan perlakuan", "Risiko kedua"]).count(), 2)
        self.assertEqual(RiskTreatment.objects.get(action_plan="Aksi risiko kedua").risk.title, "Risiko kedua")
        self.assertEqual(RiskTreatment.objects.get(action_plan="Aksi risiko pertama").risk.title, "Risiko dengan perlakuan")

        payload["treatments-0-risk_index"] = 2
        response = self.client.post(reverse("risk:risk_create"), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["treatment_formset"].forms[0].errors)
        self.assertEqual(RiskRegister.objects.filter(title__in=["Risiko dengan perlakuan", "Risiko kedua"]).count(), 2)

    def test_edit_risk_updates_existing_and_adds_inline_treatment(self):
        treatment = RiskTreatment.objects.create(risk=self.risk, action_plan="Rencana awal",
                                                created_by=self.head, updated_by=self.head)
        self.client.force_login(self.officer)
        edit_page = self.client.get(reverse("risk:risk_edit", args=[self.risk.pk]), HTTP_HOST="risk.localhost")
        self.assertContains(edit_page, 'data-evaluation-risk-select')
        self.assertContains(edit_page, 'data-treatment-risk-select')
        self.assertContains(edit_page, 'data-add-treatment-detail')
        self.assertContains(edit_page, 'id="inlineTreatmentDetailForm"')
        self.assertNotContains(edit_page, 'Tambah Perlakuan untuk Nama Risiko Lain')
        treatment_rows = edit_page.content.decode().split('id="inlineTreatmentRows"', 1)[1].split('</tbody>', 1)[0]
        self.assertEqual(treatment_rows.count('data-treatment-row'), 1)
        self.assertEqual(treatment_rows.count('data-treatment-name-cell'), 1)
        self.assertIn('name="treatments-0-expected_likelihood"', treatment_rows)
        response = self.client.post(reverse("risk:risk_edit", args=[self.risk.pk]), self._risk_with_treatments_payload([
            {"id": treatment.pk, "action_plan": "Rencana diperbarui", "expected_likelihood": 1, "expected_impact": 2},
            {"action_plan": "Rencana tambahan"},
        ], initial=1), HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.risk.treatments.count(), 2)
        treatment.refresh_from_db()
        self.assertEqual(treatment.action_plan, "Rencana diperbarui")
        self.assertEqual(treatment.expected_score, 2)
        self.assertEqual(treatment.created_by, self.head)
        self.assertEqual(treatment.updated_by, self.officer)
        self.assertTrue(ActivityLog.objects.filter(action="RISK_TREATMENT_UPDATED", target_id=str(treatment.pk)).exists())

    def test_edit_risk_shows_existing_options_without_extra_blank_row(self):
        for plan in ("Rencana pertama", "Rencana kedua"):
            RiskTreatment.objects.create(risk=self.risk, action_plan=plan,
                                         created_by=self.officer, updated_by=self.officer)
        self.client.force_login(self.officer)
        response = self.client.get(reverse("risk:risk_edit", args=[self.risk.pk]), HTTP_HOST="risk.localhost")
        rows = response.content.decode().split('id="inlineTreatmentRows"', 1)[1].split('</tbody>', 1)[0]
        self.assertEqual(rows.count('data-treatment-row'), 2)
        self.assertEqual(rows.count('data-treatment-detail-row'), 1)

    def test_create_risk_skips_deleted_treatment_and_keeps_next_row(self):
        self.client.force_login(self.officer)
        payload = self._risk_with_treatments_payload([
            {"risk_index": 99, "action_plan": "Jangan disimpan", "DELETE": "on"},
            {"option": "Pelatihan", "action_plan": "Latih petugas", "target_date": "2026-12-31",
             "responsible_person": "Risk Owner", "notes": "Tindak lanjut"},
        ])
        response = self.client.post(reverse("risk:risk_create"), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(RiskTreatment.objects.values_list("action_plan", flat=True)), ["Latih petugas"])
        self.assertIsNone(RiskTreatment.objects.get().expected_likelihood)

    def test_edit_risk_deletes_saved_inline_treatment(self):
        removed = RiskTreatment.objects.create(risk=self.risk, action_plan="Hapus ini",
                                               created_by=self.head, updated_by=self.head)
        retained = RiskTreatment.objects.create(risk=self.risk, action_plan="Tetap ada",
                                                created_by=self.head, updated_by=self.head)
        self.client.force_login(self.officer)
        payload = self._risk_with_treatments_payload([
            {"id": removed.pk, "DELETE": "on"},
            {"id": retained.pk, "action_plan": "Tetap ada"},
        ], initial=2)
        response = self.client.post(reverse("risk:risk_edit", args=[self.risk.pk]), payload,
                                    HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(RiskTreatment.objects.filter(pk=removed.pk).exists())
        self.assertTrue(RiskTreatment.objects.filter(pk=retained.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(action="RISK_TREATMENT_DELETED", target_id=str(removed.pk)).exists())

    def test_invalid_inline_treatment_prevents_risk_changes(self):
        self.client.force_login(self.officer)
        invalid = self._risk_with_treatments_payload([{"action_plan": "Rencana", "expected_likelihood": 2}])
        response = self.client.post(reverse("risk:risk_create"), invalid, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["treatment_formset"].errors)
        self.assertFalse(RiskRegister.objects.filter(title="Risiko dengan perlakuan").exists())
        old_title = self.risk.title
        response = self.client.post(reverse("risk:risk_edit", args=[self.risk.pk]), invalid, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        self.risk.refresh_from_db()
        self.assertEqual(self.risk.title, old_title)
        self.assertFalse(self.risk.treatments.exists())

    def test_inline_formset_rejects_treatment_from_another_risk(self):
        other = RiskRegister.objects.create(division=self.division_b, title="Risiko privat", category="operational",
                                            inherent_likelihood=1, inherent_impact=1, residual_likelihood=1,
                                            residual_impact=1, created_by=self.officer, updated_by=self.officer)
        treatment = RiskTreatment.objects.create(risk=other, action_plan="Jangan diubah",
                                                created_by=self.officer, updated_by=self.officer)
        self.client.force_login(self.officer)
        payload = self._risk_with_treatments_payload([{"id": treatment.pk, "action_plan": "Forged"}], initial=1)
        response = self.client.post(reverse("risk:risk_edit", args=[self.risk.pk]), payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["treatment_formset"].non_form_errors())
        treatment.refresh_from_db()
        self.assertEqual(treatment.risk, other)
        self.assertEqual(treatment.action_plan, "Jangan diubah")

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

    def _annual_download(self, user=None, **params):
        self.client.force_login(user or self.officer)
        return self.client.get(reverse("risk:annual_report"), {
            "year": self.risk.created_at.year, "division": self.division_a.pk,
            "download": "1", **params,
        }, HTTP_HOST="risk.localhost")

    def test_annual_excel_preserves_template_and_exports_selected_year(self):
        from .exports import TEMPLATE
        year = self.risk.created_at.year
        self.risk.title = "=1+1"
        self.risk.save()
        monitoring = RiskMonitoring.objects.create(
            risk=self.risk, year=year, quarter=1, initial_likelihood=4, initial_impact=4,
            final_likelihood=2, final_impact=2, expected_likelihood=2, expected_impact=2,
            updated_by=self.officer,
        )
        RiskActionPlan.objects.create(
            monitoring=monitoring, description="Rencana tahun terpilih",
            responsible_person="Pemilik", target_date=f"{year}-03-31",
            created_by=self.officer, updated_by=self.officer,
        )
        RiskActionPlan.objects.create(
            monitoring=monitoring, description="Aksi lanjutan",
            responsible_person="Pemilik", target_date=f"{year}-06-30",
            created_by=self.officer, updated_by=self.officer,
        )
        other_period = RiskMonitoring.objects.create(
            risk=self.risk, year=year - 1, quarter=1, initial_likelihood=1, initial_impact=1,
            final_likelihood=1, final_impact=1, updated_by=self.officer,
        )
        RiskActionPlan.objects.create(
            monitoring=other_period, description="Jangan ekspor tahun lain",
            responsible_person="Pemilik", created_by=self.officer, updated_by=self.officer,
        )
        response = self._annual_download()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        payload = b"".join(response.streaming_content)
        exported = load_workbook(BytesIO(payload), data_only=False)
        values = load_workbook(BytesIO(payload), data_only=True)
        original = load_workbook(TEMPLATE)
        self.assertEqual(exported.sheetnames, original.sheetnames)
        self.assertEqual(exported["Identifikasi Risiko"]["B10"].value, self.risk.risk_code)
        self.assertEqual(exported["Identifikasi Risiko"]["D10"].value, "=1+1")
        self.assertEqual(exported["Identifikasi Risiko"]["D10"].data_type, "s")
        self.assertEqual(exported["Identifikasi Risiko"]["B7"].value, "Kode Risiko")
        self.assertEqual(exported["Identifikasi Risiko"]["C7"].value, "Sasaran Terkait")
        self.assertEqual(exported["Identifikasi Risiko"]["D7"].value, "Nama Risiko")
        self.assertEqual(values["Identifikasi Risiko"]["K10"].value, 16)
        self.assertEqual(values["Pemantauan TW1"]["S10"].value, 0)
        self.assertEqual(values["Pemantauan TW1"]["C10"].value, "Rencana tahun terpilih")
        self.assertEqual(values["Pemantauan TW1"]["E10"].value.date().isoformat(), f"{year}-03-31")
        self.assertEqual(values["Pemantauan TW1"]["E11"].value.date().isoformat(), f"{year}-06-30")
        self.assertEqual(values["Identifikasi Risiko"]["C4"].value, self.division_a.name)
        for name in exported.sheetnames[3:]:
            self.assertEqual(exported[name]["A7"].value, original[name]["A7"].value)
            if name != "Identifikasi Risiko":
                self.assertEqual(exported[name].column_dimensions["B"].width, original[name].column_dimensions["B"].width)
        with ZipFile(BytesIO(payload)) as actual, ZipFile(TEMPLATE) as source:
            for name in ["xl/styles.xml", "xl/theme/theme1.xml", "xl/drawings/drawing1.xml", *[f"xl/worksheets/sheet{i}.xml" for i in (1, 2, 3)]]:
                self.assertEqual(actual.read(name), source.read(name))
        self.assertNotIn("Jangan ekspor tahun lain", str(list(values["Pemantauan TW1"].values)))
        exported.close()
        values.close()
        original.close()

    def test_annual_excel_includes_every_control_and_risk_code(self):
        from .services import _groups

        self.risk.existing_controls = "Pengendalian pertama"
        self.risk.control_effectiveness = "adequate"
        self.risk.save(update_fields=["existing_controls", "control_effectiveness"])
        RiskControl.objects.create(
            risk=self.risk, position=2, description="Pengendalian kedua",
            effectiveness="effective", notes="Bukti kontrol kedua",
        )
        response = self._annual_download()
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(b"".join(response.streaming_content)), data_only=True)
        identification = workbook["Identifikasi Risiko"]
        evaluation = workbook["Analisis & Evaluasi Risiko"]
        self.assertEqual(identification["B10"].value, self.risk.risk_code)
        self.assertEqual(identification["D10"].value, self.risk.title)
        self.assertEqual(evaluation["B7"].value, "Kode Risiko / Nama Risiko")
        self.assertEqual(evaluation["B10"].value, f"{self.risk.risk_code}\n{self.risk.title}")
        self.assertEqual(evaluation["C10"].value, "Pengendalian pertama")
        self.assertEqual(evaluation["E10"].value, "ü")
        self.assertEqual(evaluation["C11"].value, "Pengendalian kedua")
        self.assertEqual(evaluation["F11"].value, "ü")
        self.assertEqual(evaluation["L11"].value, "Bukti kontrol kedua")
        self.assertEqual(_groups(identification, start_row=10, title_column=4)[0]["title"], self.risk.title)
        workbook.close()

    def test_annual_excel_restricts_division_and_validates_year(self):
        response = self._annual_download(division=self.division_b.pk)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.streaming)
        self.assertTrue(response.context["form"].errors)
        response = self._annual_download(year="invalid")
        self.assertTrue(response.context["form"].errors)
        response = self._annual_download(year=2020)
        self.assertContains(response, "Tidak ada data risiko")
        self.assertEqual(ActivityLog.objects.filter(
            actor=self.officer, action="ANNUAL_REPORT_DOWNLOAD_FAILED", success=False,
        ).count(), 3)
        self.assertFalse(ActivityLog.objects.filter(action="ANNUAL_REPORT_DOWNLOADED").exists())

    def test_annual_excel_all_divisions_respects_user_access(self):
        other = RiskRegister.objects.create(
            division=self.division_b, title="Risiko Divisi B", category="financial",
            description="Uraian", cause="Penyebab", impact="Dampak",
            risk_owner="Pemilik", created_by=self.officer, updated_by=self.officer,
        )
        manager = get_user_model().objects.create_user(username="annual-manager", role="risk")
        RiskAccess.objects.create(user=manager, role="manager_member")

        response = self._annual_download(user=manager, division="")
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(b"".join(response.streaming_content)), data_only=True)
        rows = list(workbook["Identifikasi Risiko"].values)
        titles = [str(row[3]) for row in rows if row[3]]
        self.assertEqual(workbook["Identifikasi Risiko"]["C4"].value, "Semua Divisi")
        self.assertIn(self.risk.title, titles)
        self.assertIn(other.title, titles)
        workbook.close()
        self.assertIsNone(ActivityLog.objects.filter(
            actor=manager, action="ANNUAL_REPORT_DOWNLOADED",
        ).latest("pk").metadata["division_id"])

        response = self._annual_download(division="")
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(b"".join(response.streaming_content)), data_only=True)
        titles = [str(row[3]) for row in workbook["Identifikasi Risiko"].values if row[3]]
        self.assertIn(self.risk.title, titles)
        self.assertNotIn(other.title, titles)
        workbook.close()

    def test_download_audit_records_actor_document_and_request_once(self):
        self.client.force_login(self.officer)
        url = reverse("risk:annual_report")
        self.client.get(url, HTTP_HOST="risk.localhost")
        self.assertFalse(ActivityLog.objects.filter(category="RISK").exists())
        started = timezone.now()
        response = self.client.get(url, {
            "year": self.risk.created_at.year, "division": self.division_a.pk, "download": "1",
        }, HTTP_HOST="risk.localhost", REMOTE_ADDR="192.0.2.10", HTTP_USER_AGENT="Audit test browser")
        self.assertTrue(response.streaming)
        log = ActivityLog.objects.get(category="RISK")
        self.assertEqual(log.action, "ANNUAL_REPORT_DOWNLOADED")
        self.assertEqual(log.actor, self.officer)
        self.assertEqual(log.actor_username, "officer")
        self.assertGreaterEqual(log.created_at, started)
        self.assertEqual(log.ip_address, "192.0.2.10")
        self.assertEqual(log.user_agent, "Audit test browser")
        self.assertEqual(log.metadata["year"], self.risk.created_at.year)
        self.assertEqual(log.metadata["division_id"], self.division_a.pk)
        self.assertEqual(log.metadata["risk_count"], 1)
        self.assertEqual(log.metadata["delivery"], "response_prepared")
        self.assertEqual(log.metadata["path"], url)
        self.assertIn(log.metadata["filename"], response["Content-Disposition"])
        self.assertEqual(log.target_label, log.metadata["filename"])
        self.assertTrue(log.success)

    def test_view_audit_records_visible_risk_and_report_filters(self):
        self.client.force_login(self.officer)
        response = self.client.get(reverse("risk:risk_detail", args=[self.risk.pk]), HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        log = ActivityLog.objects.get(action="RISK_VIEWED")
        self.assertEqual(log.target_id, str(self.risk.pk))
        self.assertEqual(log.target_label, self.risk.risk_code)
        self.client.get(reverse("risk:risk_list"), {"year": self.risk.created_at.year}, HTTP_HOST="risk.localhost")
        self.assertEqual(ActivityLog.objects.get(action="RISK_REGISTER_VIEWED").metadata["year"], str(self.risk.created_at.year))
        self.client.get(reverse("risk:monitoring_report"), {"year": 2026, "quarter": 2}, HTTP_HOST="risk.localhost")
        log = ActivityLog.objects.get(action="MONITORING_REPORT_VIEWED")
        self.assertEqual(log.metadata["year"], 2026)
        self.assertEqual(log.metadata["quarter"], 2)
        other = RiskRegister.objects.create(
            division=self.division_b, title="Rahasia", category="operational",
            inherent_likelihood=1, inherent_impact=1, residual_likelihood=1, residual_impact=1,
            created_by=self.officer, updated_by=self.officer,
        )
        response = self.client.get(reverse("risk:risk_detail", args=[other.pk]), HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ActivityLog.objects.filter(action="RISK_VIEWED").count(), 1)

    def test_download_mark_identifies_each_recipient_without_changing_sheets(self):
        from .exports import DOWNLOAD_MARK_SALT, annual_risk_workbook

        self.officer.first_name = "Rina & <PWU>"
        self.officer.save()
        baseline = annual_risk_workbook([self.risk], division=self.division_a, year=self.risk.created_at.year)
        marks = []
        for user in (self.officer, self.officer, self.head):
            response = self._annual_download(user=user)
            payload = b"".join(response.streaming_content)
            book = load_workbook(BytesIO(payload))
            properties = {prop.name: prop.value for prop in book.custom_doc_props}
            book.close()
            mark = signing.loads(properties["RiskDownloadProvenance"], salt=DOWNLOAD_MARK_SALT)
            marks.append(mark)
            self.assertEqual(mark["username"], user.username)
            self.assertEqual(mark["user_id"], str(user.pk))
            self.assertEqual(mark["full_name"], user.get_full_name() or user.username)
            self.assertEqual(properties["RiskDownloadedBy"], mark["username"])
            self.assertEqual(properties["RiskDownloaderName"], mark["full_name"])
            self.assertEqual(properties["RiskDownloadedAt"], mark["downloaded_at"])
            self.assertEqual(datetime.fromisoformat(mark["downloaded_at"]).utcoffset().total_seconds(), 7 * 3600)
            log = ActivityLog.objects.get(action="ANNUAL_REPORT_DOWNLOADED", metadata__download_mark__download_id=mark["download_id"])
            self.assertEqual(log.actor, user)
            self.assertEqual(log.metadata["download_mark"], mark)
            token = properties["RiskDownloadProvenance"]
            with self.assertRaises(signing.BadSignature):
                signing.loads(token + "tampered", salt=DOWNLOAD_MARK_SALT)
            with ZipFile(BytesIO(payload)) as marked, ZipFile(baseline) as original:
                for name in original.namelist():
                    if name not in {"docProps/custom.xml", "_rels/.rels", "[Content_Types].xml"}:
                        self.assertEqual(marked.read(name), original.read(name), name)
                # Excel must be able to discover the custom properties part.
                rels = ElementTree.fromstring(marked.read("_rels/.rels"))
                self.assertEqual(sum(rel.attrib["Type"].endswith("/custom-properties") for rel in rels), 1)
                types = ElementTree.fromstring(marked.read("[Content_Types].xml"))
                self.assertEqual(sum(node.attrib.get("PartName") == "/docProps/custom.xml" for node in types), 1)
        self.assertEqual(len({mark["download_id"] for mark in marks}), 3)
        baseline.close()

    def test_annual_excel_adds_fourth_quarter_without_sample_rows(self):
        RiskMonitoring.objects.create(
            risk=self.risk, year=self.risk.created_at.year, quarter=4,
            initial_likelihood=4, initial_impact=4, final_likelihood=2, final_impact=2,
            updated_by=self.officer,
        )
        response = self._annual_download(user=self.head)
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(b"".join(response.streaming_content)), data_only=True)
        self.assertIn("Pemantauan TW4", workbook.sheetnames)
        self.assertEqual(workbook["Pemantauan TW4"]["B10"].value, f"{self.risk.risk_code}\n{self.risk.title}")
        self.assertIsNone(workbook["Pemantauan TW4"]["B16"].value)
        self.assertEqual(workbook["Pemantauan TW4"]["M10"].value, 4)
        workbook.close()

    def test_register_sorting_applies_before_pagination_and_keeps_filters(self):
        for index in range(21):
            RiskRegister.objects.create(
                division=self.division_a, title=f"Risiko {index:02}", category="operational",
                description="Uraian", cause="Sebab", impact="Dampak", risk_owner="Pemilik",
                inherent_likelihood=1, inherent_impact=1,
                residual_likelihood=5 if index == 20 else 1, residual_impact=5,
                created_by=self.officer, updated_by=self.officer,
            )
        self.client.force_login(self.officer)
        response = self.client.get(reverse("risk:risk_list"), {
            "sort": "residual", "order": "desc", "q": "Risiko", "division": self.division_a.pk,
        }, HTTP_HOST="risk.localhost")
        page = response.context["page_obj"]
        self.assertEqual(page[0].title, "Risiko 20")
        self.assertEqual(page.paginator.count, 21)
        self.assertContains(response, "sort=residual&amp;order=desc")
        self.assertIn("division=", response.context["pagination_query"])
        ascending = self.client.get(reverse("risk:risk_list"), {
            "sort": "residual", "order": "asc", "q": "Risiko",
        }, HTTP_HOST="risk.localhost")
        self.assertEqual(ascending.context["page_obj"][0].residual_score, 5)

    def test_register_level_filter_matches_criteria_matrix(self):
        scores = {
            (1, 2): "Sangat Rendah", (1, 3): "Rendah",
            (2, 2): "Rendah", (1, 5): "Tinggi",
            (3, 3): "Sedang", (2, 5): "Tinggi",
            (4, 4): "Tinggi", (4, 5): "Sangat Tinggi",
        }
        for index, ((likelihood, impact), _level) in enumerate(scores.items()):
            RiskRegister.objects.create(
                division=self.division_a, title=f"Boundary {index}", category="operational",
                description="Uraian", cause="Sebab", impact="Dampak", risk_owner="Pemilik",
                inherent_likelihood=1, inherent_impact=1,
                residual_likelihood=likelihood, residual_impact=impact,
                created_by=self.officer, updated_by=self.officer,
            )
        self.client.force_login(self.officer)
        for level in ("Sangat Rendah", "Rendah", "Sedang", "Tinggi", "Sangat Tinggi"):
            with self.subTest(level=level):
                response = self.client.get(
                    reverse("risk:risk_list"), {"level": level.lower()}, HTTP_HOST="risk.localhost",
                )
                found = {risk.title for risk in response.context["page_obj"]}
                expected = {
                    f"Boundary {index}" for index, expected_level in enumerate(scores.values())
                    if expected_level == level
                }
                if level == "Sedang":
                    expected.add(self.risk.title)
                self.assertEqual(found, expected)
        unknown = self.client.get(
            reverse("risk:risk_list"), {"level": "unknown"}, HTTP_HOST="risk.localhost",
        )
        self.assertEqual(unknown.context["page_obj"].paginator.count, 0)

    def test_monitoring_sorting_keeps_actions_grouped_and_missing_targets_last(self):
        other = RiskRegister.objects.create(
            division=self.division_a, title="Autre risque", category="operational",
            description="Uraian", cause="Sebab", impact="Dampak", risk_owner="Pemilik",
            inherent_likelihood=1, inherent_impact=1, residual_likelihood=1, residual_impact=1,
            created_by=self.officer, updated_by=self.officer,
        )
        missing = RiskMonitoring.objects.create(
            risk=other, year=2026, quarter=2, initial_likelihood=1, initial_impact=1,
            final_likelihood=1, final_impact=1, updated_by=self.officer,
        )
        monitoring = RiskMonitoring.objects.create(
            risk=self.risk, year=2026, quarter=2, initial_likelihood=4, initial_impact=4,
            final_likelihood=3, final_impact=3, expected_likelihood=2, expected_impact=2,
            updated_by=self.officer,
        )
        for description in ("Z aksi", "A aksi"):
            RiskActionPlan.objects.create(
                monitoring=monitoring, description=description, responsible_person="Pemilik",
                created_by=self.officer, updated_by=self.officer,
            )
        self.client.force_login(self.officer)
        for direction in ("asc", "desc"):
            response = self.client.get(reverse("risk:monitoring_report"), {
                "year": 2026, "quarter": 2, "sort": "expected_score", "order": direction,
            }, HTTP_HOST="risk.localhost")
            self.assertEqual([m.pk for m in response.context["monitorings"]], [monitoring.pk, missing.pk])
        response = self.client.get(reverse("risk:monitoring_report"), {
            "year": 2026, "quarter": 2, "sort": "plan", "order": "asc",
        }, HTTP_HOST="risk.localhost")
        self.assertEqual(response.context["monitorings"][0].pk, monitoring.pk)
        self.assertEqual([a.description for a in response.context["monitorings"][0].action_plans.all()], ["A aksi", "Z aksi"])
        self.assertContains(response, "year=2026&amp;quarter=2")

    def test_dashboard_uses_database_summary(self):
        self.client.force_login(self.officer)

        response = self.client.get(
            reverse("risk:dashboard"),
            HTTP_HOST="risk.localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_risks"], 1)
        self.assertEqual(response.context["open_risks"], 1)
        self.assertEqual(response.context["level_counts"]["Sedang"], 1)
        self.assertContains(response, "Kembali ke Portal Utama")
        self.assertContains(response, ">Keluar<")

    def test_all_likelihood_impact_pairs_follow_criteria_matrix(self):
        rows = (
            ("Sangat Rendah", "Sangat Rendah", "Rendah", "Rendah", "Sedang"),
            ("Sangat Rendah", "Rendah", "Sedang", "Sedang", "Tinggi"),
            ("Rendah", "Sedang", "Sedang", "Tinggi", "Tinggi"),
            ("Sedang", "Sedang", "Tinggi", "Tinggi", "Sangat Tinggi"),
            ("Tinggi", "Tinggi", "Tinggi", "Sangat Tinggi", "Sangat Tinggi"),
        )
        for impact, row in enumerate(rows, 1):
            for likelihood, level in enumerate(row, 1):
                with self.subTest(likelihood=likelihood, impact=impact):
                    self.assertEqual(RiskRegister.level_for(likelihood, impact), level)
        self.assertEqual(RiskRegister.level_for(1, 5), "Tinggi")
        self.assertEqual(RiskTreatment(expected_likelihood=1, expected_impact=5).expected_level, "Tinggi")
        monitoring = RiskMonitoring(
            initial_likelihood=1, initial_impact=5,
            final_likelihood=1, final_impact=5,
            expected_likelihood=1, expected_impact=5,
        )
        self.assertEqual((monitoring.initial_level, monitoring.final_level, monitoring.expected_level),
                         ("Tinggi", "Tinggi", "Tinggi"))

    def test_high_impact_low_likelihood_is_high_with_identification_score(self):
        self.risk.residual_likelihood = 1
        self.risk.residual_impact = 5
        self.risk.save()
        self.client.force_login(self.officer)
        self.assertEqual(self.risk.risk_level, "Tinggi")
        listing = self.client.get(reverse("risk:risk_list"), {"level": "tinggi"}, HTTP_HOST="risk.localhost")
        self.assertIn(self.risk, listing.context["page_obj"])
        self.assertNotContains(listing, "Skor Risiko")
        self.assertNotContains(listing, "Skor 5 / 25")
        detail = self.client.get(reverse("risk:risk_detail", args=[self.risk.pk]), HTTP_HOST="risk.localhost")
        self.assertContains(detail, "Kemungkinan 1 · Dampak 5")
        self.assertContains(detail, "Skor Risiko")
        self.assertContains(detail, ">16</td>")
        editor = self.client.get(reverse("risk:risk_edit", args=[self.risk.pk]), HTTP_HOST="risk.localhost")
        self.assertContains(editor, "Skor Risiko")
        self.assertContains(editor, 'id="inherentScore"')
        guide = self.client.get(reverse("risk:criteria"), HTTP_HOST="risk.localhost")
        self.assertEqual(guide.context["matrix"][0]["cells"][0]["level"], "Tinggi")
        dashboard = self.client.get(reverse("risk:dashboard"), HTTP_HOST="risk.localhost")
        self.assertEqual(dashboard.context["level_counts"]["Tinggi"], 1)

    def test_excel_level_uses_likelihood_and_impact_matrix(self):
        from .exports import _risk_values

        values = _risk_values(1, 5, "H", "I", 10)
        self.assertEqual(values[3].value, "Tinggi")
        self.assertIn("CHOOSE(I10", values[3].expression)
        self.assertIn("CHOOSE(H10", values[3].expression)

    def test_matrix_colors_follow_reference_and_hide_range_legend(self):
        self.client.force_login(self.officer)
        response = self.client.get(reverse("risk:criteria"), HTTP_HOST="risk.localhost")
        self.assertEqual([[cell["color"] for cell in row["cells"]] for row in response.context["matrix"]], [
            ["orange", "orange", "orange", "red", "red"],
            ["yellow", "yellow", "orange", "orange", "red"],
            ["green", "yellow", "yellow", "orange", "orange"],
            ["blue", "green", "yellow", "yellow", "orange"],
            ["blue", "blue", "green", "green", "yellow"],
        ])
        self.assertContains(response, 'class="matrix-cell matrix-', count=25)
        for legend in ("1–2 Sangat Rendah", "3–4 Rendah", "5–9 Sedang", "10–16 Tinggi", "17–25 Sangat Tinggi"):
            self.assertNotContains(response, legend)

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
        self.assertEqual(ActivityLog.objects.filter(action="RISK_WORKBOOK_IMPORTED", actor=self.officer, success=True).count(), 2)
        self.assertEqual(ActivityLog.objects.filter(action="RISK_WORKBOOK_IMPORTED").first().metadata["filename"], "Manajemen Risiko 2026.xlsx")

    def test_downloaded_empty_template_can_be_filled_and_imported(self):
        self.client.force_login(self.officer)
        page = self.client.get(reverse("risk:workbook_import"), HTTP_HOST="risk.localhost")
        self.assertContains(page, reverse("risk:workbook_import_template"))
        self.assertContains(page, "risk-import-file")
        self.assertContains(page, "Download Template Excel")

        response = self.client.get(reverse("risk:workbook_import_template"), HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertIn(".xlsx", response["Content-Disposition"])
        workbook = load_workbook(BytesIO(b"".join(response.streaming_content)))
        self.assertIn("Pemantauan TW4", workbook.sheetnames)
        sheet = workbook["Identifikasi Risiko"]
        self.assertIsNone(sheet["C4"].value)
        self.assertIsNone(sheet["B10"].value)
        self.assertIsNone(sheet["D10"].value)
        self.assertEqual(sheet["B7"].value, "Kode Risiko")
        self.assertEqual(sheet["C7"].value, "Sasaran Terkait")
        self.assertEqual(sheet["D7"].value, "Nama Risiko")
        self.assertIsNone(workbook["Analisis & Evaluasi Risiko"]["B10"].value)

        sheet["C4"] = self.division_a.name
        sheet["D10"] = "Risiko dari template kosong"
        sheet["F10"] = "Sebab risiko"
        sheet["H10"] = "Dampak risiko"
        sheet["I10"] = 2
        sheet["J10"] = 3
        stream = BytesIO()
        workbook.save(stream)
        workbook.close()
        upload = SimpleUploadedFile("Template Impor Manajemen Risiko 2026.xlsx", stream.getvalue())
        imported = self.client.post(
            reverse("risk:workbook_import"), {"workbook": upload}, HTTP_HOST="risk.localhost",
        )
        self.assertEqual(imported.status_code, 302)
        self.assertTrue(RiskRegister.objects.filter(
            division=self.division_a, title="Risiko dari template kosong",
        ).exists())

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
        self.assertTrue(ActivityLog.objects.filter(action="RISK_WORKBOOK_IMPORT_FAILED", actor=self.officer, success=False).exists())

    def test_read_only_division_cannot_be_used_for_creation_or_import(self):
        division_c = RiskDivision.objects.create(code="C", name="Divisi C")
        RiskAccess.objects.create(user=self.officer, role="risk_officer", division=division_c)
        RiskAccess.objects.create(user=self.officer, role="division_head", division=self.division_b)
        RiskAccess.objects.create(user=self.head, role="risk_officer", division=self.division_b)
        self.client.force_login(self.officer)

        create_url = reverse("risk:risk_create")
        page = self.client.get(create_url, HTTP_HOST="risk.localhost")
        choices = page.context["form"].fields["division"].queryset
        self.assertEqual(set(choices.values_list("pk", flat=True)), {self.division_a.pk, division_c.pk})
        payload = {
            "division": self.division_b.pk, "title": "Risiko tanpa hak tulis",
            "cause": "Penyebab", "impact": "Dampak",
            "inherent_likelihood": 2, "inherent_impact": 2,
            "residual_likelihood": 2, "residual_impact": 2,
        }
        response = self.client.post(create_url, payload, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertIn("division", response.context["form"].errors)
        self.assertFalse(RiskRegister.objects.filter(title=payload["title"]).exists())

        workbook = Workbook()
        workbook.active.title = "Identifikasi Risiko"
        workbook.active["C4"] = self.division_b.name
        stream = BytesIO()
        workbook.save(stream)
        workbook.close()
        upload = SimpleUploadedFile("Risiko 2026.xlsx", stream.getvalue())
        response = self.client.post(
            reverse("risk:workbook_import"), {"workbook": upload}, HTTP_HOST="risk.localhost",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tidak memiliki akses impor")

    def test_detail_quarter_table_creates_updates_and_validates_monitoring(self):
        url = reverse("risk:risk_detail", args=[self.risk.pk])
        self.client.force_login(self.officer)
        page = self.client.get(url, {"monitoring_year": 2026}, HTTP_HOST="risk.localhost")
        self.assertContains(page, 'name="q1-initial_likelihood"')
        self.assertNotContains(page, 'name="q4-final_impact"')
        self.assertContains(page, "Pemantauan Triwulan I - 2026")
        self.assertContains(page, "Selanjutnya &gt;")
        next_page = self.client.get(url, {"monitoring_year": 2026, "monitoring_quarter": 2}, HTTP_HOST="risk.localhost")
        self.assertContains(next_page, "Pemantauan Triwulan II - 2026")
        self.assertContains(next_page, 'name="q2-final_impact"')
        self.assertNotContains(next_page, 'name="q1-initial_likelihood"')
        self.assertContains(page, "Rencana Aksi Perlakuan Risiko")
        self.assertContains(page, "Level Risiko Sebelum Perlakuan")
        self.assertContains(page, "Deviasi")
        self.assertContains(page, "Tambah Baris Rencana Aksi")
        self.assertContains(page, "Simpan Triwulan I")
        self.assertContains(page, 'name="q1-evaluation_notes"')
        self.assertNotContains(page, 'name="q1-business_environment_changes"')
        self.assertNotContains(page, "Register Risiko")

        data = {
            "monitoring_year": "2026", "save_quarter": "1",
            "q1-initial_likelihood": "4", "q1-initial_impact": "4",
            "q1-final_likelihood": "3", "q1-final_impact": "2",
            "q1-expected_likelihood": "2", "q1-expected_impact": "2",
            "q1-evaluation_notes": "Mitigasi berjalan dan perubahan pasar",
            "q1-actions-TOTAL_FORMS": "2", "q1-actions-INITIAL_FORMS": "0",
            "q1-actions-MIN_NUM_FORMS": "0", "q1-actions-MAX_NUM_FORMS": "1000",
            "q1-actions-0-description": "Perbarui SOP",
            "q1-actions-0-realization": "SOP sudah disusun",
            "q1-actions-0-target_date": "2026-03-31",
            "q1-actions-0-responsible_person": "Petugas A",
            "q1-actions-1-description": "Sosialisasi SOP",
            "q1-actions-1-responsible_person": "Petugas B",
        }
        invalid = self.client.post(url, {**data, "q1-final_impact": "6"}, HTTP_HOST="risk.localhost")
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, "6")
        self.assertFalse(RiskMonitoring.objects.filter(risk=self.risk, year=2026, quarter=1).exists())

        created = self.client.post(url, data, HTTP_HOST="risk.localhost")
        self.assertEqual(created.status_code, 302)
        monitoring = RiskMonitoring.objects.get(risk=self.risk, year=2026, quarter=1)
        self.assertEqual(monitoring.final_score, 6)
        self.assertEqual(monitoring.evaluation_notes, "Mitigasi berjalan dan perubahan pasar")
        self.assertEqual(monitoring.business_environment_changes, "")
        actions = list(monitoring.action_plans.order_by("pk"))
        self.assertEqual([action.description for action in actions], ["Perbarui SOP", "Sosialisasi SOP"])
        self.assertEqual(actions[0].realization, "SOP sudah disusun")
        self.assertTrue(ActivityLog.objects.filter(action="MONITORING_CREATED", target_id=str(monitoring.pk)).exists())
        monitoring.business_environment_changes = "Perubahan lama"
        monitoring.save(update_fields=["business_environment_changes"])
        page = self.client.get(url, {"monitoring_year": 2026}, HTTP_HOST="risk.localhost")
        self.assertEqual(
            page.context["monitoring_rows"][0]["form"].initial["evaluation_notes"],
            "Mitigasi berjalan dan perubahan pasar\nPerubahan lama",
        )
        updated_data = {
            **data, "q1-final_impact": "1",
            "q1-evaluation_notes": "Mitigasi berjalan dan perubahan pasar\nPerubahan lama",
            "q1-actions-TOTAL_FORMS": "3", "q1-actions-INITIAL_FORMS": "2",
            "q1-actions-0-id": str(actions[0].pk), "q1-actions-1-id": str(actions[1].pk),
            "q1-actions-0-description": "SOP final",
        }
        updated = self.client.post(url, updated_data, HTTP_HOST="risk.localhost")
        self.assertEqual(updated.status_code, 302)
        monitoring.refresh_from_db()
        self.assertEqual(monitoring.final_score, 3)
        self.assertEqual(monitoring.business_environment_changes, "")
        self.assertEqual(monitoring.action_plans.order_by("pk").first().description, "SOP final")
        self.assertEqual(RiskMonitoring.objects.filter(risk=self.risk, year=2026, quarter=1).count(), 1)
        self.assertTrue(ActivityLog.objects.filter(action="MONITORING_UPDATED", target_id=str(monitoring.pk)).exists())
        removed = self.client.post(url, {**updated_data, "q1-actions-1-DELETE": "on"}, HTTP_HOST="risk.localhost")
        self.assertEqual(removed.status_code, 302)
        self.assertEqual(monitoring.action_plans.count(), 1)

        empty_action_quarter = self.client.post(url, {
            "monitoring_year": "2026", "save_quarter": "2",
            "q2-initial_likelihood": "3", "q2-initial_impact": "3",
            "q2-final_likelihood": "2", "q2-final_impact": "2",
            "q2-actions-TOTAL_FORMS": "1", "q2-actions-INITIAL_FORMS": "0",
            "q2-actions-MIN_NUM_FORMS": "0", "q2-actions-MAX_NUM_FORMS": "1000",
        }, HTTP_HOST="risk.localhost")
        self.assertEqual(empty_action_quarter.status_code, 302)
        self.assertFalse(RiskMonitoring.objects.get(
            risk=self.risk, year=2026, quarter=2,
        ).action_plans.exists())

        self.client.force_login(self.head)
        read_only = self.client.get(url, {"monitoring_year": 2026}, HTTP_HOST="risk.localhost")
        self.assertContains(read_only, "SOP final")
        denied = self.client.post(url, data, HTTP_HOST="risk.localhost")
        self.assertEqual(denied.status_code, 403)

    def test_monitoring_action_rows_follow_risk_treatments(self):
        treatments = [RiskTreatment.objects.create(
            risk=self.risk, action_plan=plan, responsible_person="Pemilik",
            created_by=self.officer, updated_by=self.officer,
        ) for plan in ("Perlakuan pertama", "Perlakuan kedua")]
        self.client.force_login(self.officer)
        url = reverse("risk:risk_detail", args=[self.risk.pk])
        page = self.client.get(url, {"monitoring_year": 2026}, HTTP_HOST="risk.localhost")
        forms = page.context["monitoring_rows"][0]["action_formset"].forms
        self.assertEqual([form.initial["description"] for form in forms], [
            "Perlakuan pertama", "Perlakuan kedua",
        ])
        self.assertTrue(all(form.is_treatment_linked for form in forms))

        data = {
            "monitoring_year": "2026", "save_quarter": "1",
            "q1-initial_likelihood": "4", "q1-initial_impact": "4",
            "q1-final_likelihood": "2", "q1-final_impact": "2",
            "q1-actions-TOTAL_FORMS": "2", "q1-actions-INITIAL_FORMS": "0",
            "q1-actions-MIN_NUM_FORMS": "0", "q1-actions-MAX_NUM_FORMS": "1000",
        }
        for index, treatment in enumerate(treatments):
            data.update({
                f"q1-actions-{index}-treatment": str(treatment.pk),
                f"q1-actions-{index}-description": treatment.action_plan,
                f"q1-actions-{index}-responsible_person": "Pemilik",
            })
        response = self.client.post(url, data, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        monitoring = RiskMonitoring.objects.get(risk=self.risk, year=2026, quarter=1)
        self.assertEqual(list(monitoring.action_plans.order_by("pk").values_list("treatment_id", flat=True)), [
            treatment.pk for treatment in treatments
        ])

        treatments[0].action_plan = "Perlakuan pertama diperbarui"
        treatments[0].save(update_fields=["action_plan"])
        self.assertEqual(monitoring.action_plans.order_by("pk").first().description,
                         "Perlakuan pertama diperbarui")
        page = self.client.get(url, {"monitoring_year": 2026}, HTTP_HOST="risk.localhost")
        self.assertEqual(page.context["monitoring_rows"][0]["action_formset"].forms[0].initial["description"],
                         "Perlakuan pertama diperbarui")
        linked_action = monitoring.action_plans.order_by("pk").first()
        edit_url = reverse("risk:action_edit", args=[linked_action.pk])
        edit_page = self.client.get(edit_url, HTTP_HOST="risk.localhost")
        self.assertContains(edit_page, "Rencana ini mengikuti Perlakuan Risiko")
        self.assertContains(edit_page, 'disabled')
        forged_edit = self.client.post(edit_url, {
            "description": "Rencana yang diganti dari pemantauan",
            "responsible_person": "Pemilik", "status": "planned", "progress": "0",
        }, HTTP_HOST="risk.localhost")
        self.assertEqual(forged_edit.status_code, 302)
        linked_action.refresh_from_db()
        self.assertEqual(linked_action.description, "Perlakuan pertama diperbarui")
        third = RiskTreatment.objects.create(
            risk=self.risk, action_plan="Perlakuan ketiga", responsible_person="Pemilik",
            created_by=self.officer, updated_by=self.officer,
        )
        page = self.client.get(url, {"monitoring_year": 2026}, HTTP_HOST="risk.localhost")
        forms = page.context["monitoring_rows"][0]["action_formset"].forms
        self.assertEqual(len(forms), 3)
        self.assertEqual(forms[-1].initial["treatment"], third.pk)
        existing_actions = list(monitoring.action_plans.order_by("pk"))
        updated_data = {
            **data,
            "q1-actions-TOTAL_FORMS": "3", "q1-actions-INITIAL_FORMS": "2",
        }
        for index, action in enumerate(existing_actions):
            updated_data.update({
                f"q1-actions-{index}-id": str(action.pk),
                f"q1-actions-{index}-treatment": str(action.treatment_id),
                f"q1-actions-{index}-description": action.description,
                f"q1-actions-{index}-responsible_person": action.responsible_person,
            })
        updated_data.update({
            "q1-actions-2-treatment": str(third.pk),
            "q1-actions-2-description": "Teks yang diganti dari pemantauan",
            "q1-actions-2-responsible_person": "Pemilik",
        })
        response = self.client.post(url, updated_data, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(monitoring.action_plans.order_by("pk").values_list("description", flat=True)), [
            "Perlakuan pertama diperbarui", "Perlakuan kedua", "Perlakuan ketiga",
        ])

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

    def test_activity_log_filters_downloads_and_displays_jakarta_time(self):
        response = self._annual_download()
        log = ActivityLog.objects.get(action="ANNUAL_REPORT_DOWNLOADED")
        ActivityLog.objects.create(
            actor=self.head, actor_username=self.head.username, category="RISK",
            action="RISK_UPDATED", description="Another action",
        )
        admin = get_user_model().objects.create_superuser(username="audit-admin", password="test-pass-123")
        self.client.force_login(admin)
        today = timezone.localtime(log.created_at).date().isoformat()
        response = self.client.get(reverse("risk:activity_log"), {
            "actor": self.officer.pk, "action": log.action, "result": "success",
            "date_from": today, "date_to": today,
        }, HTTP_HOST="risk.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"]), [log])
        self.assertContains(response, "Waktu (WIB)")
        self.assertContains(response, timezone.localtime(log.created_at).strftime("%d/%m/%Y %H:%M:%S"))
        self.assertContains(response, log.target_label)
        self.assertContains(response, log.description)

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
