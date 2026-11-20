from datetime import date, datetime
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Assignment, ChecklistGroup, ChecklistItem


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
        self.group = ChecklistGroup.objects.create(assignment=self.assignment, title="Tugas")

    def test_month_and_division_filter_board(self):
        self.client.force_login(self.other)
        url = reverse("monitoring:board")
        shown = self.client.get(url, {"month": "2026-11", "division": "Divisi Aset"}, HTTP_HOST="monitor.localhost")
        self.assertEqual(shown.status_code, 200)
        self.assertContains(shown, "Laporan aset")
        carried = self.client.get(url, {"month": "2026-12"}, HTTP_HOST="monitor.localhost")
        self.assertContains(carried, "Laporan aset")
        self.assertContains(carried, "Lanjutan dari November 2026")
        self.assertEqual(self.client.get(url, {"month": "bad"}, HTTP_HOST="monitor.localhost").status_code, 404)

    def test_task_links_use_opaque_public_id(self):
        self.client.force_login(self.other)
        detail_url = reverse("monitoring:assignment_detail", args=[self.assignment.public_id])
        self.assertEqual(uuid.UUID(detail_url.strip("/").split("/")[-1]), self.assignment.public_id)
        self.assertEqual(self.client.get(f"/tugas/{self.assignment.pk}/", HTTP_HOST="monitor.localhost").status_code, 404)
        board = self.client.get(reverse("monitoring:board"), {"month": "2026-11"}, HTTP_HOST="monitor.localhost")
        self.assertContains(board, detail_url)
        self.assertNotContains(board, f'href="/tugas/{self.assignment.pk}/"')
        listing = self.client.get(reverse("monitoring:assignment_list"), HTTP_HOST="monitor.localhost")
        self.assertContains(listing, detail_url)

    def test_edit_controls_are_on_detail_for_active_members(self):
        detail_url = reverse("monitoring:assignment_detail", args=[self.assignment.public_id])
        edit_url = reverse("monitoring:assignment_edit", args=[self.assignment.public_id])
        self.client.force_login(self.responsible)
        editable = self.client.get(detail_url, HTTP_HOST="monitor.localhost")
        self.assertContains(editable, "Edit Tugas &amp; Checklist")
        self.assertNotContains(editable, 'name="title"')
        self.client.force_login(self.other)
        other_detail = self.client.get(detail_url, HTTP_HOST="monitor.localhost")
        self.assertContains(other_detail, "Edit Tugas &amp; Checklist")
        self.assertNotContains(other_detail, 'name="title"')
        edit_detail = self.client.get(detail_url, {"edit": "1"}, HTTP_HOST="monitor.localhost")
        self.assertContains(edit_detail, 'class="task-main-panel task-edit-mode"')
        self.assertContains(edit_detail, 'name="title"')
        self.assertContains(edit_detail, '<textarea name="title"')
        self.assertContains(edit_detail, 'form="assignment-edit-form"')
        self.assertContains(edit_detail, 'Hapus tugas')
        self.assertContains(edit_detail, '<button type="submit">+ Checklist</button>')
        self.assertNotContains(edit_detail, 'Nama checklist')
        self.assertNotContains(edit_detail, 'Isi checklist')
        self.assertNotContains(edit_detail, 'Nama grup baru')
        self.assertNotContains(edit_detail, 'class="task-editor-content"')
        self.assertEqual(edit_detail.content.count(b'class="task-main-panel'), 1)
        self.assertRedirects(self.client.get(edit_url, HTTP_HOST="monitor.localhost"), f"{detail_url}?edit=1#edit-tugas", fetch_redirect_response=False)
        payload = {
            "title": "Laporan aset diperbarui", "description": "Catatan baru", "month": "2026-11",
            "start_date": "2026-11-02", "due_date": "2026-11-20", "division": "Divisi Aset",
            "responsible": self.responsible.pk, "status": "doing",
        }
        saved = self.client.post(detail_url, payload, HTTP_HOST="monitor.localhost")
        self.assertRedirects(saved, f"{detail_url}?edit=1#edit-tugas", fetch_redirect_response=False)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.title, "Laporan aset diperbarui")
        self.assertEqual(self.assignment.status, "doing")
        payload["due_date"] = "2026-11-01"
        invalid = self.client.post(detail_url, payload, HTTP_HOST="monitor.localhost")
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, 'class="task-main-panel task-edit-mode"')
        self.assertContains(invalid, "Tenggat tidak boleh sebelum tanggal mulai")

    def test_delete_task_is_post_only_and_removes_checklist(self):
        self.client.force_login(self.other)
        delete_url = reverse("monitoring:assignment_delete", args=[self.assignment.public_id])
        self.assertEqual(self.client.get(delete_url, HTTP_HOST="monitor.localhost").status_code, 405)
        ChecklistItem.objects.create(assignment=self.assignment, group=self.group, text="Cek dokumen")
        response = self.client.post(delete_url, HTTP_HOST="monitor.localhost")
        self.assertRedirects(response, "/?month=2026-11&division=Divisi+Aset", fetch_redirect_response=False)
        self.assertFalse(Assignment.objects.filter(pk=self.assignment.pk).exists())
        self.assertFalse(ChecklistGroup.objects.filter(pk=self.group.pk).exists())
        self.assertEqual(ChecklistItem.objects.count(), 0)

    def test_carried_task_stops_after_completion_month(self):
        self.client.force_login(self.responsible)
        completed_in_december = timezone.make_aware(datetime(2026, 12, 10, 9, 0))
        with patch("monitoring.models.timezone.now", return_value=completed_in_december):
            self.assignment.status = "done"
            self.assignment.save(update_fields=["status", "updated_at"])
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, "done")
        self.assertEqual(self.assignment.completed_at, completed_in_december)
        december = self.client.get(reverse("monitoring:board"), {"month": "2026-12"}, HTTP_HOST="monitor.localhost")
        january = self.client.get(reverse("monitoring:board"), {"month": "2027-01"}, HTTP_HOST="monitor.localhost")
        self.assertContains(december, "Laporan aset")
        self.assertNotContains(january, "Laporan aset")

    def test_checklist_can_be_checked_in_detail_and_managed_in_edit(self):
        add_url = reverse("monitoring:checklist_add", args=[self.assignment.public_id, self.group.pk])
        self.client.force_login(self.other)
        detail_url = reverse("monitoring:assignment_detail", args=[self.assignment.public_id])
        self.assertNotContains(self.client.get(detail_url, HTTP_HOST="monitor.localhost"), add_url)
        self.client.force_login(self.responsible)
        added = self.client.post(add_url, {"steps": "  Periksa data  \nKirim laporan"}, HTTP_HOST="monitor.localhost")
        self.assertRedirects(added, f"{detail_url}?edit=1#edit-tugas", fetch_redirect_response=False)
        self.assertEqual(ChecklistItem.objects.filter(assignment=self.assignment).count(), 2)
        item = ChecklistItem.objects.get(assignment=self.assignment, text="Periksa data")
        self.assertEqual(item.text, "Periksa data")
        detail = self.client.get(reverse("monitoring:assignment_detail", args=[self.assignment.public_id]), HTTP_HOST="monitor.localhost")
        self.assertContains(detail, ">Tugas</h3>")
        self.assertContains(detail, '<ol class="task-checklist">')
        self.assertContains(detail, 'role="progressbar"')
        self.assertContains(detail, "Kirim laporan")
        self.assertNotContains(detail, "<h2>Checklist</h2>")
        edit_url = reverse("monitoring:checklist_edit", args=[self.assignment.public_id, item.pk])
        self.assertNotContains(detail, add_url)
        self.assertNotContains(detail, edit_url)
        edit_detail = self.client.get(detail_url, {"edit": "1"}, HTTP_HOST="monitor.localhost")
        self.assertContains(edit_detail, add_url)
        self.assertContains(edit_detail, edit_url)
        self.assertEqual(self.client.post(edit_url, {"text": "  Periksa ulang data  "}, HTTP_HOST="monitor.localhost").status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.text, "Periksa ulang data")
        board = self.client.get(reverse("monitoring:board"), {"month": "2026-11"}, HTTP_HOST="monitor.localhost")
        self.assertContains(board, "Checklist 0/2")
        toggle_url = reverse("monitoring:checklist_toggle", args=[self.assignment.public_id, item.pk])
        self.assertNotContains(board, toggle_url)
        self.assertContains(detail, toggle_url)
        self.assertNotContains(edit_detail, toggle_url)
        response = self.client.post(toggle_url, {"return_month": "2026-12"}, HTTP_HOST="monitor.localhost")
        self.assertRedirects(response, reverse("monitoring:assignment_detail", args=[self.assignment.public_id]), fetch_redirect_response=False)
        item.refresh_from_db()
        self.assertTrue(item.is_done)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(toggle_url, HTTP_HOST="monitor.localhost").status_code, 302)
        self.assertEqual(self.client.post(edit_url, {"text": "Diperbarui anggota lain"}, HTTP_HOST="monitor.localhost").status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.text, "Diperbarui anggota lain")

    def test_checklist_group_titles_can_be_added_and_renamed(self):
        self.client.force_login(self.responsible)
        rename_url = reverse("monitoring:checklist_group_edit", args=[self.assignment.public_id, self.group.pk])
        self.assertEqual(self.client.post(rename_url, {"title": "Aset"}, HTTP_HOST="monitor.localhost").status_code, 302)
        self.group.refresh_from_db()
        self.assertEqual(self.group.title, "Aset")
        add_group_url = reverse("monitoring:checklist_group_add", args=[self.assignment.public_id])
        invalid_group = self.client.post(add_group_url, {"title": "Tanpa isi"}, HTTP_HOST="monitor.localhost")
        self.assertEqual(invalid_group.status_code, 302)
        self.assertFalse(ChecklistGroup.objects.filter(assignment=self.assignment, title="Tanpa isi").exists())
        self.assertEqual(self.client.post(add_group_url, {"title": "User", "steps": "Hubungi user\nCek akun"}, HTTP_HOST="monitor.localhost").status_code, 302)
        user_group = ChecklistGroup.objects.get(assignment=self.assignment, title="User")
        self.assertEqual(list(user_group.items.values_list("text", flat=True)), ["Hubungi user", "Cek akun"])
        add_url = reverse("monitoring:checklist_add", args=[self.assignment.public_id, self.group.pk])
        self.assertEqual(self.client.post(add_url, {"steps": "Cek aset"}, HTTP_HOST="monitor.localhost").status_code, 302)
        detail = self.client.get(reverse("monitoring:assignment_detail", args=[self.assignment.public_id]), HTTP_HOST="monitor.localhost")
        self.assertContains(detail, ">Aset</h3>")
        self.assertContains(detail, ">User</h3>")
        self.assertContains(detail, '<ol class="task-checklist">', count=2)
        edit_detail = self.client.get(reverse("monitoring:assignment_detail", args=[self.assignment.public_id]), {"edit": "1"}, HTTP_HOST="monitor.localhost")
        self.assertContains(edit_detail, 'value="Aset"')
        self.assertContains(edit_detail, 'value="User"')
        self.assertContains(edit_detail, reverse("monitoring:checklist_group_delete", args=[self.assignment.public_id, self.group.pk]))
        self.assertContains(detail, reverse("monitoring:checklist_toggle", args=[self.assignment.public_id, ChecklistItem.objects.first().pk]))
        board = self.client.get(reverse("monitoring:board"), {"month": "2026-11"}, HTTP_HOST="monitor.localhost")
        self.assertContains(board, "Cek aset")
        self.assertContains(board, "Hubungi user")
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(rename_url, {"title": "Diperbarui anggota lain"}, HTTP_HOST="monitor.localhost").status_code, 302)
        delete_group_url = reverse("monitoring:checklist_group_delete", args=[self.assignment.public_id, self.group.pk])
        self.assertEqual(self.client.post(delete_group_url, HTTP_HOST="monitor.localhost").status_code, 302)
        self.assertFalse(ChecklistGroup.objects.filter(pk=self.group.pk).exists())
        self.assertFalse(ChecklistItem.objects.filter(text="Cek aset").exists())

    def test_add_checklist_creates_editable_card_with_first_task(self):
        self.client.force_login(self.other)
        add_url = reverse("monitoring:checklist_group_add", args=[self.assignment.public_id])
        detail_url = reverse("monitoring:assignment_detail", args=[self.assignment.public_id])
        self.assertEqual(self.client.get(add_url, HTTP_HOST="monitor.localhost").status_code, 405)
        first = self.client.post(add_url, HTTP_HOST="monitor.localhost")
        group = ChecklistGroup.objects.get(assignment=self.assignment, title="Checklist 2")
        item = group.items.get(text="Task 1")
        self.assertRedirects(first, f"{detail_url}?edit=1#checklist-group-{group.pk}", fetch_redirect_response=False)
        edit_detail = self.client.get(detail_url, {"edit": "1"}, HTTP_HOST="monitor.localhost")
        self.assertContains(edit_detail, f'id="checklist-group-{group.pk}"')
        self.assertContains(edit_detail, 'value="Checklist 2"')
        self.assertContains(edit_detail, 'value="Task 1"')
        self.assertContains(edit_detail, reverse("monitoring:checklist_edit", args=[self.assignment.public_id, item.pk]))
        self.client.post(add_url, HTTP_HOST="monitor.localhost")
        self.assertTrue(ChecklistGroup.objects.filter(assignment=self.assignment, title="Checklist 3").exists())

    def test_task_table_search_and_filters(self):
        self.client.force_login(self.other)
        url = reverse("monitoring:assignment_list")
        shown = self.client.get(url, {"q": "laporan", "month": "2026-12", "division": "Divisi Aset", "status": "todo"}, HTTP_HOST="monitor.localhost")
        self.assertEqual(shown.status_code, 200)
        self.assertContains(shown, "Laporan aset")
        hidden = self.client.get(url, {"q": "laporan", "division": "Divisi Keuangan"}, HTTP_HOST="monitor.localhost")
        self.assertNotContains(hidden, "Laporan aset")
        self.assertEqual(self.client.get(url, {"status": "invalid"}, HTTP_HOST="monitor.localhost").status_code, 404)

    def test_active_members_can_update_status(self):
        url = reverse("monitoring:assignment_status", args=[self.assignment.public_id])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, {"status": "done"}, HTTP_HOST="monitor.localhost").status_code, 302)
        self.client.force_login(self.responsible)
        self.assertEqual(self.client.get(url, HTTP_HOST="monitor.localhost").status_code, 405)
        response = self.client.post(url, {"status": "doing", "return_month": "2026-12"}, HTTP_HOST="monitor.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertIn("month=2026-12", response["Location"])
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
        self.assertEqual(list(created.checklist_groups.values_list("title", flat=True)), ["Tugas"])

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
