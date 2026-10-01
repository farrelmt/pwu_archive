from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import ActivityLog

from .models import CompanyMember, InventoryAccess, InventoryItem, InventoryReport


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}, ROOT_URLCONF="inventory.host_urls")
class InventoryPermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username="inv-manager", password="test-pass-123", role="inventory")
        self.viewer = User.objects.create_user(username="inv-viewer", password="test-pass-123", role="inventory")
        self.superuser = User.objects.create_superuser(username="inv-admin", password="test-pass-123")
        InventoryAccess.objects.create(user=self.manager, role="manager")
        InventoryAccess.objects.create(user=self.viewer, role="participant")
        self.member = self.viewer.company_member_profile
        self.member.employee_id = "EMP-001"
        self.member.full_name = "Budi"
        self.member.division = "TI"
        self.member.position = "Staff"
        self.member.save()
        self.item = InventoryItem.objects.create(
            asset_code="AST-001", item_name="Laptop", category="hardware",
            specifications="16 GB RAM", received_date="2026-01-10",
            purchase_price=Decimal("12000000"), quantity=1, condition="good",
            status="assigned", assigned_to=self.member,
            created_by=self.manager, updated_by=self.manager,
        )

    def test_manager_can_open_edit_page(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("inventory:item_edit", args=[self.item.pk]), HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 200)

    def test_manager_dashboard_uses_database_summary(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("inventory:dashboard"),
            HTTP_HOST="inventory.localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["item_count"], 1)
        self.assertEqual(response.context["assigned_count"], 1)
        self.assertEqual(response.context["maintenance_count"], 0)
        self.assertEqual(response.context["total_value"], Decimal("12000000"))

    def test_member_list_supports_sorting_and_shows_all_current_members(self):
        User = get_user_model()
        zeta = User.objects.create(username="division_zeta", first_name="Zeta", role="employee")
        alpha = User.objects.create(username="division_alpha", first_name="Alpha", role="employee")
        zeta.company_member_profile.employee_id = "NIP-900"
        zeta.company_member_profile.save(update_fields=["employee_id"])
        alpha.company_member_profile.employee_id = "NIP-100"
        alpha.company_member_profile.save(update_fields=["employee_id"])
        self.client.force_login(self.manager)

        name_response = self.client.get(
            reverse("inventory:member_list") + "?sort=full_name&direction=asc&per_page=100",
            HTTP_HOST="inventory.localhost",
        )
        names = [member.full_name for member in name_response.context["page_obj"]]
        self.assertEqual(names, sorted(names, key=str.casefold))
        self.assertEqual(
            name_response.context["page_obj"].paginator.count,
            User.objects.count(),
        )

        nip_response = self.client.get(
            reverse("inventory:member_list") + "?sort=employee_id&direction=desc&per_page=100",
            HTTP_HOST="inventory.localhost",
        )
        employee_ids = [member.employee_id for member in nip_response.context["page_obj"]]
        self.assertEqual(employee_ids, sorted(employee_ids, reverse=True))
        self.assertContains(nip_response, "anggota ditemukan")

    def test_member_list_has_working_pagination_controls(self):
        User = get_user_model()
        for number in range(18):
            User.objects.create(
                username=f"pagination_{number:02d}",
                first_name=f"Pagination {number:02d}",
                role="employee",
            )
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("inventory:member_list") + "?per_page=20",
            HTTP_HOST="inventory.localhost",
        )

        expected_pages = (User.objects.count() + 19) // 20
        self.assertEqual(
            response.context["page_obj"].paginator.num_pages,
            expected_pages,
        )
        self.assertEqual(
            len(response.context["page_obj"]),
            min(User.objects.count(), 20),
        )
        self.assertContains(response, "Berikutnya")
        self.assertContains(response, "page=2")

    def test_participant_is_read_only(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("inventory:item_edit", args=[self.item.pk]), HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 403)

    def test_member_detail_lists_assigned_item(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("inventory:member_detail", args=[self.member.pk]), HTTP_HOST="inventory.localhost")
        self.assertContains(response, "AST-001")
        self.assertContains(response, "Laporkan Barang Rusak")
        self.assertNotContains(response, reverse("inventory:report_create", args=[self.item.pk]))

    def test_participant_dashboard_redirects_to_own_inventory(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("inventory:dashboard"), HTTP_HOST="inventory.localhost")

        self.assertRedirects(
            response,
            reverse("inventory:member_detail", args=[self.member.pk]),
            fetch_redirect_response=False,
        )

    def test_participant_cannot_open_another_members_inventory(self):
        other_member = CompanyMember.objects.create(
            employee_id="EMP-002", full_name="Pegawai Lain",
            division="Keuangan", position="Staff",
        )
        self.client.force_login(self.viewer)

        response = self.client.get(
            reverse("inventory:member_detail", args=[other_member.pk]),
            HTTP_HOST="inventory.localhost",
        )

        self.assertEqual(response.status_code, 403)

    def test_participant_cannot_open_management_lists(self):
        self.client.force_login(self.viewer)

        member_response = self.client.get(reverse("inventory:member_list"), HTTP_HOST="inventory.localhost")
        item_response = self.client.get(reverse("inventory:item_list"), HTTP_HOST="inventory.localhost")

        self.assertEqual(member_response.status_code, 403)
        self.assertEqual(item_response.status_code, 403)

    def test_participant_navigation_is_simple(self):
        self.client.force_login(self.viewer)

        response = self.client.get(
            reverse("inventory:member_detail", args=[self.member.pk]),
            HTTP_HOST="inventory.localhost",
        )

        self.assertContains(response, "Inventaris Saya")
        self.assertContains(response, ">Keluar<")
        self.assertContains(response, "Log Out")
        self.assertNotContains(response, ">Ringkasan<")
        self.assertNotContains(response, ">Anggota Perusahaan<")
        self.assertNotContains(response, ">Barang &amp; Hardware<")
        self.assertNotContains(response, "Pengaturan")

    def test_member_detail_groups_all_it_inventory(self):
        InventoryItem.objects.create(
            asset_code="IT-MOUSE-01", item_name="Mouse Wireless", category="peripheral",
            received_date="2026-01-10", purchase_price=Decimal("250000"),
            status="assigned", assigned_to=self.member,
            created_by=self.manager, updated_by=self.manager,
        )
        InventoryItem.objects.create(
            asset_code="SW-OFFICE-01", item_name="Microsoft Office", category="software",
            model="2026", serial_number="LICENSE-001", received_date="2026-01-10",
            purchase_price=Decimal("1500000"), status="assigned",
            assigned_to=self.member, created_by=self.manager, updated_by=self.manager,
        )
        self.client.force_login(self.viewer)

        response = self.client.get(
            reverse("inventory:member_detail", args=[self.member.pk]),
            HTTP_HOST="inventory.localhost",
        )

        self.assertContains(response, ">Hardware<")
        self.assertContains(response, ">Software<")
        self.assertContains(response, "AST-001")
        self.assertContains(response, "IT-MOUSE-01")
        self.assertContains(response, "SW-OFFICE-01")

    def test_participant_can_only_open_own_item_detail(self):
        other_member = CompanyMember.objects.create(
            employee_id="EMP-002", full_name="Pegawai Lain",
            division="Keuangan", position="Staff",
        )
        other_item = InventoryItem.objects.create(
            asset_code="AST-002", item_name="Laptop Lain", category="computer",
            received_date="2026-01-10", status="assigned", assigned_to=other_member,
            created_by=self.manager, updated_by=self.manager,
        )
        self.client.force_login(self.viewer)

        own_response = self.client.get(
            reverse("inventory:item_detail", args=[self.item.pk]),
            HTTP_HOST="inventory.localhost",
        )
        other_response = self.client.get(
            reverse("inventory:item_detail", args=[other_item.pk]),
            HTTP_HOST="inventory.localhost",
        )

        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(other_response.status_code, 403)

    def test_add_it_inventory_link_prefills_member_and_category(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("inventory:item_create")
            + f"?member={self.member.pk}&category=software",
            HTTP_HOST="inventory.localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["assigned_to"], self.member)
        self.assertEqual(response.context["form"].initial["status"], "assigned")
        self.assertEqual(response.context["form"].initial["category"], "software")

    def test_section_add_links_and_personal_category_defaults(self):
        for user, route in ((self.viewer, "personal_item_create"), (self.manager, "item_create")):
            self.client.force_login(user)
            response = self.client.get(
                reverse("inventory:member_detail", args=[self.member.pk]),
                HTTP_HOST="inventory.localhost",
            )
            html = response.content.decode()
            self.assertLess(html.index(">Inventaris</h2>"), html.index(">Hardware</h2>"))
            self.assertContains(response, "+ Tambah Inventaris</a>", count=3)
            for category in ("office", "computer", "software"):
                query = f"?category={category}" if route == "personal_item_create" else f"?member={self.member.pk}&amp;category={category}"
                self.assertContains(response, reverse(f"inventory:{route}") + query)
        self.client.force_login(self.viewer)
        for category in ("office", "computer", "software"):
            response = self.client.get(
                reverse("inventory:personal_item_create") + f"?category={category}",
                HTTP_HOST="inventory.localhost",
            )
            self.assertEqual(response.context["form"].initial["category"], category)

    def test_superuser_personal_inventory_setup_and_add(self):
        self.client.force_login(self.superuser)
        url = reverse("inventory:my_inventory")
        response = self.client.get(url, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CompanyMember.objects.filter(user=self.superuser).exists())
        member = CompanyMember.objects.get(user=self.superuser)
        self.assertContains(response, "+ Tambah Inventaris Saya</a>", count=3)
        for category in ("office", "computer", "software"):
            self.assertContains(response, reverse("inventory:personal_item_create") + f"?category={category}")
        response = self.client.post(reverse("inventory:personal_item_create"), {
            "item_name": "Pulpen Admin", "category": "office",
            "received_date": "2026-09-29", "condition": "good",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InventoryItem.objects.get(item_name="Pulpen Admin").assigned_to, member)

    def test_portal_member_identity_is_synchronized_to_inventory(self):
        self.viewer.first_name = "Budi"
        self.viewer.last_name = "Santoso"
        self.viewer.email = "budi@pwujatim.site"
        self.viewer.phone = "08123456789"
        self.viewer.is_active = False
        self.viewer.save()

        self.member.refresh_from_db()
        self.assertEqual(self.member.full_name, "Budi Santoso")
        self.assertEqual(self.member.email, "budi@pwujatim.site")
        self.assertEqual(self.member.phone, "08123456789")
        self.assertEqual(self.member.status, "inactive")

    def test_total_value(self):
        self.assertEqual(self.item.total_value, Decimal("12000000"))

    def test_participant_can_report_own_item(self):
        self.client.force_login(self.viewer)

        response = self.client.post(
            reverse("inventory:report_create", args=[self.item.pk]),
            {"report_type": "damaged", "description": "Laptop tidak dapat menyala."},
            HTTP_HOST="inventory.localhost",
        )

        report = InventoryReport.objects.get(item=self.item)
        self.assertRedirects(
            response,
            reverse("inventory:report_list"),
            fetch_redirect_response=False,
        )
        self.assertEqual(report.reporter, self.viewer)
        self.assertEqual(report.status, "reported")

    def test_participant_cannot_report_another_members_item(self):
        other_member = CompanyMember.objects.create(
            employee_id="EMP-002", full_name="Pegawai Lain",
            division="Keuangan", position="Staff",
        )
        other_item = InventoryItem.objects.create(
            asset_code="AST-002", item_name="Laptop Lain", category="computer",
            received_date="2026-01-10", status="assigned", assigned_to=other_member,
            created_by=self.manager, updated_by=self.manager,
        )
        self.client.force_login(self.viewer)

        response = self.client.get(
            reverse("inventory:report_create", args=[other_item.pk]),
            HTTP_HOST="inventory.localhost",
        )

        self.assertEqual(response.status_code, 403)

    def test_only_superuser_can_advance_report_workflow(self):
        report = InventoryReport.objects.create(
            item=self.item,
            reporter=self.viewer,
            report_type="complaint",
            description="Perangkat lambat.",
        )
        self.client.force_login(self.manager)
        denied_response = self.client.post(
            reverse("inventory:report_advance", args=[report.pk]),
            HTTP_HOST="inventory.localhost",
        )
        self.assertEqual(denied_response.status_code, 403)

        self.client.force_login(self.superuser)
        expected_statuses = ["verified", "proposed", "handed_over", "resolved"]
        for expected_status in expected_statuses:
            response = self.client.post(
                reverse("inventory:report_advance", args=[report.pk]),
                HTTP_HOST="inventory.localhost",
            )
            self.assertRedirects(
                response,
                reverse("inventory:report_list"),
                fetch_redirect_response=False,
            )
            report.refresh_from_db()
            self.assertEqual(report.status, expected_status)

        self.assertIsNotNone(report.resolved_at)

    def test_participant_can_add_own_inventory(self):
        self.client.force_login(self.viewer)

        response = self.client.post(
            reverse("inventory:personal_item_create"),
            {
                "item_name": "Keyboard Pribadi",
                "category": "peripheral",
                "brand": "Logitech",
                "model": "K120",
                "serial_number": "KEY-001",
                "specifications": "USB",
                "received_date": "2026-09-28",
                "condition": "good",
                "notes": "Dipakai untuk bekerja.",
            },
            HTTP_HOST="inventory.localhost",
        )

        created_item = InventoryItem.objects.get(item_name="Keyboard Pribadi")
        self.assertRedirects(
            response,
            reverse("inventory:member_detail", args=[self.member.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(created_item.assigned_to, self.member)
        self.assertEqual(created_item.created_by, self.viewer)
        self.assertEqual(created_item.status, "assigned")
        self.assertTrue(created_item.asset_code.startswith("PRIBADI-"))

    def test_participant_only_sees_own_reports(self):
        InventoryReport.objects.create(
            item=self.item, reporter=self.viewer, report_type="damaged",
            description="Laporan saya.",
        )
        InventoryReport.objects.create(
            item=self.item, reporter=self.manager, report_type="complaint",
            description="Laporan orang lain.",
        )
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("inventory:report_list"), HTTP_HOST="inventory.localhost")

        self.assertContains(response, "Laporan saya.")
        self.assertNotContains(response, "Laporan orang lain.")


    def test_section_rejects_unrelated_category_and_preserves_errors(self):
        for user, route in ((self.viewer, "personal_item_create"), (self.manager, "item_create")):
            self.client.force_login(user)
            for section, invalid in (("software", "furniture"), ("computer", "software"), ("office", "computer")):
                url = reverse(f"inventory:{route}") + f"?category={section}"
                response = self.client.post(url, {"item_name": "Invalid", "category": invalid}, HTTP_HOST="inventory.localhost")
                self.assertEqual(response.status_code, 200)
                self.assertIn("category", response.context["form"].errors)
                self.assertNotIn(invalid, dict(response.context["form"].fields["category"].choices))
        self.assertFalse(InventoryItem.objects.filter(item_name="Invalid").exists())

    def test_minimal_item_and_optional_date(self):
        for user, route in ((self.viewer, "personal_item_create"), (self.manager, "item_create")):
            self.client.force_login(user)
            url = reverse(f"inventory:{route}") + "?category=office"
            response = self.client.get(url, HTTP_HOST="inventory.localhost")
            self.assertNotIn("serial_number", response.context["form"].fields)
            self.assertContains(response, "inventory-date-button")
            response = self.client.post(url, {"item_name": route, "received_date": "", "serial_number": "ignored"}, HTTP_HOST="inventory.localhost")
            self.assertEqual(response.status_code, 302)
            item = InventoryItem.objects.get(item_name=route)
            self.assertIsNone(item.received_date)
            self.assertEqual(item.category, "office")
            self.assertEqual(item.serial_number, "")
            self.assertEqual(item.quantity, 1)
            self.assertEqual(item.purchase_price, 0)
            response = self.client.post(url, {}, HTTP_HOST="inventory.localhost")
            self.assertIn("item_name", response.context["form"].errors)

    def test_new_report_menu_limits_item_selection(self):
        other = InventoryItem.objects.create(asset_code="OTHER", item_name="Other", category="office", created_by=self.manager, updated_by=self.manager)
        self.client.force_login(self.viewer)
        url = reverse("inventory:report_new")
        response = self.client.get(url, HTTP_HOST="inventory.localhost")
        self.assertEqual(list(response.context["form"].fields["item"].queryset), [self.item])
        response = self.client.post(url, {"item": other.pk, "report_type": "damaged", "description": "Broken"}, HTTP_HOST="inventory.localhost")
        self.assertIn("item", response.context["form"].errors)
        response = self.client.post(url, {"item": self.item.pk, "report_type": "damaged", "description": "Broken"}, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InventoryReport.objects.get().item, self.item)
        report = InventoryReport.objects.get()
        self.assertTrue(ActivityLog.objects.filter(
            actor=self.viewer,
            category="INVENTORY",
            action="REPORT_CREATED",
            target_id=str(report.pk),
        ).exists())

    def test_only_superuser_can_open_inventory_activity_log(self):
        self.client.force_login(self.viewer)
        denied = self.client.get(
            reverse("inventory:activity_log"),
            HTTP_HOST="inventory.localhost",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("inventory:activity_log"),
            HTTP_HOST="inventory.localhost",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log Aktivitas")

    def test_photo_upload_storage_and_permissions(self):
        from io import BytesIO
        from tempfile import TemporaryDirectory
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.viewer)
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            image = BytesIO()
            Image.new("RGB", (20, 20), "blue").save(image, format="PNG")
            photo = SimpleUploadedFile("test.png", image.getvalue(), content_type="image/png")
            response = self.client.post(reverse("inventory:personal_item_create") + "?category=office", {"item_name": "Photo item", "photo": photo}, HTTP_HOST="inventory.localhost")
            self.assertEqual(response.status_code, 302)
            item = InventoryItem.objects.get(item_name="Photo item")
            self.assertTrue(item.photo.name.startswith("inventory/photos/"))
            self.assertTrue(item.photo.storage.exists(item.photo.name))
            url = reverse("inventory:item_photo", args=[item.pk])
            response = self.client.get(url, HTTP_HOST="inventory.localhost")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/jpeg")
            list(response.streaming_content)
            self.client.force_login(self.manager)
            response = self.client.get(url, HTTP_HOST="inventory.localhost")
            self.assertEqual(response.status_code, 200)
            list(response.streaming_content)
            outsider = get_user_model().objects.create_user(username="outsider", role="inventory")
            InventoryAccess.objects.create(user=outsider, role="participant")
            self.client.force_login(outsider)
            self.assertEqual(self.client.get(url, HTTP_HOST="inventory.localhost").status_code, 403)
            self.client.logout()
            self.assertEqual(self.client.get(url, HTTP_HOST="inventory.localhost").status_code, 302)

    def test_invalid_photo_and_oversized_photo_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .forms import PersonalInventoryItemForm
        form = PersonalInventoryItemForm({"item_name": "Bad"}, {"photo": SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")}, section="inventaris")
        self.assertFalse(form.is_valid())
        self.assertIn("photo", form.errors)
        from io import BytesIO
        from PIL import Image
        image = BytesIO()
        Image.new("RGB", (10, 10)).save(image, format="PNG")
        photo = SimpleUploadedFile("large.png", image.getvalue() + b"0" * (5 * 1024 * 1024), content_type="image/png")
        form = PersonalInventoryItemForm({"item_name": "Large"}, {"photo": photo}, section="inventaris")
        self.assertFalse(form.is_valid())
        self.assertIn("photo", form.errors)


    def test_laptop_and_computer_are_separate_hardware_categories(self):
        self.client.force_login(self.viewer)
        url = reverse("inventory:personal_item_create") + "?category=computer"
        response = self.client.get(url, HTTP_HOST="inventory.localhost")
        choices = dict(response.context["form"].fields["category"].choices)
        self.assertEqual(choices["computer"], "Komputer")
        self.assertEqual(choices["laptop"], "Laptop")
        response = self.client.post(url, {"item_name": "Laptop Test", "category": "laptop"}, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item = InventoryItem.objects.get(item_name="Laptop Test")
        response = self.client.get(reverse("inventory:member_detail", args=[self.member.pk]), HTTP_HOST="inventory.localhost")
        self.assertIn(item, response.context["hardware_items"])
        self.assertNotIn(item, response.context["other_items"])
        response = self.client.post(reverse("inventory:personal_item_create") + "?category=software", {"item_name": "Invalid laptop", "category": "laptop"}, HTTP_HOST="inventory.localhost")
        self.assertIn("category", response.context["form"].errors)
