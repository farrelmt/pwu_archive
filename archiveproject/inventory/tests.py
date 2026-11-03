from decimal import Decimal
from datetime import timedelta
from importlib import import_module
from io import BytesIO
from types import SimpleNamespace

from django.apps import apps
from django.conf import settings
from django.db import connection
from openpyxl import load_workbook
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import ActivityLog

from .forms import category_section
from .credentials import decrypt_software_password
from .models import CompanyMember, InternetPackageHistory, InternetSimCard, InventoryAccess, InventoryItem, InventoryReport, InventoryRequest


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

    def test_manager_can_view_everyones_requests_but_not_activity_log(self):
        entry = InventoryRequest.objects.create(
            requester=self.viewer, request_type="procurement", purpose="Peralatan kantor",
            items=[{"description": "Kertas", "stock": "0", "quantity": "2", "unit": "rim", "notes": ""}],
            applicant_name="Budi", division="TI",
        )
        self.client.force_login(self.manager)
        listing = self.client.get(reverse("inventory:request_list"), HTTP_HOST="inventory.localhost")
        self.assertContains(listing, "Peralatan kantor")
        detail = self.client.get(reverse("inventory:request_detail", args=[entry.public_id]), HTTP_HOST="inventory.localhost")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(self.client.get(reverse("inventory:activity_log"), HTTP_HOST="inventory.localhost").status_code, 403)

        officer = get_user_model().objects.create_user(username="inv-officer", password="test-pass-123", role="inventory")
        InventoryAccess.objects.create(user=officer, role="officer")
        self.client.force_login(officer)
        self.assertEqual(self.client.get(reverse("inventory:internet_list"), HTTP_HOST="inventory.localhost").status_code, 403)
        self.assertEqual(self.client.get(reverse("inventory:request_detail", args=[entry.public_id]), HTTP_HOST="inventory.localhost").status_code, 403)

    def test_manager_can_open_edit_page(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("inventory:item_edit", args=[self.item.pk]), HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("inventory:item_delete", args=[self.item.pk]))
        self.assertContains(response, 'id="id_purchase_date"')
        self.assertContains(response, 'id="id_received_date_same_as_purchase"')

    def test_internet_allows_manager_superuser_and_it(self):
        url = reverse("inventory:internet_list")
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse("inventory:dashboard"), HTTP_HOST="inventory.localhost", follow=True
        )
        self.assertNotContains(response, url)
        self.assertEqual(self.client.get(url, HTTP_HOST="inventory.localhost").status_code, 403)

        self.client.force_login(self.manager)
        response = self.client.get(reverse("inventory:dashboard"), HTTP_HOST="inventory.localhost")
        self.assertContains(response, url)
        self.assertEqual(self.client.get(url, HTTP_HOST="inventory.localhost").status_code, 200)

        it_user, _ = get_user_model().objects.get_or_create(
            username="it_pwu", defaults={"role": "admin"}
        )
        InventoryAccess.objects.update_or_create(user=it_user, defaults={"role": "participant", "is_active": True})
        self.client.force_login(it_user)
        response = self.client.get(url, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.item.asset_code)
        self.assertContains(response, f'href="{url}"')

        self.client.force_login(self.superuser)
        response = self.client.get(url, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{url}"')

    def test_modem_wifi_category_populates_internet_automatically(self):
        InventoryItem.objects.create(
            asset_code="AST-OLD-MODEM", item_name="Modem Lama", category="network",
            created_by=self.manager, updated_by=self.manager,
        )
        self.client.force_login(self.manager)
        create_url = reverse("inventory:item_create")
        form_page = self.client.get(
            f"{create_url}?category=modem_wifi", HTTP_HOST="inventory.localhost"
        )
        self.assertContains(form_page, 'value="modem_wifi" selected')
        self.assertEqual(form_page.context["form"].fields["item_type"].initial, "hardware")
        response = self.client.post(create_url, {
            "item_name": "Modem Kantor", "category": "modem_wifi",
            "location": "Ruang SPI", "serial_number": "MODEM-001",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        modem = InventoryItem.objects.get(item_name="Modem Kantor")
        self.assertEqual(modem.category, "modem_wifi")

        self.client.force_login(self.superuser)
        url = reverse("inventory:internet_list")
        response = self.client.get(url, HTTP_HOST="inventory.localhost")
        self.assertContains(response, "Modem Kantor")
        self.assertContains(response, "Modem Lama")
        self.assertContains(response, "Ruang SPI")
        self.assertNotContains(response, "AST-001")

        modem.category = "network"
        modem.item_name = "Perangkat Jaringan Lain"
        modem.save(update_fields=["category", "item_name"])
        response = self.client.get(url, HTTP_HOST="inventory.localhost")
        self.assertNotContains(response, "Modem Kantor")
        self.assertContains(response, "Modem Lama")

    def test_router_modem_sim_and_package_history(self):
        modem = InventoryItem.objects.create(
            asset_code="MODEM-HISTORY-1", item_name="Router Modem Kantor",
            category="modem_wifi", created_by=self.manager, updated_by=self.manager,
        )
        url = reverse("inventory:internet_detail", args=[modem.pk])
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(url, HTTP_HOST="inventory.localhost").status_code, 403)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(url, {}, HTTP_HOST="inventory.localhost").status_code, 403)

        it_user = get_user_model().objects.create_user(
            username="it_pwu", password="test-pass-123", role="admin"
        )
        InventoryAccess.objects.create(user=it_user, role="participant")
        self.client.force_login(it_user)
        empty = self.client.get(url, HTTP_HOST="inventory.localhost")
        self.assertContains(empty, "Belum ada kartu SIM")
        self.assertContains(empty, "Tambah Kartu SIM")
        self.assertNotContains(empty, "Simpan Riwayat")

        sim_response = self.client.post(url, {
            "form_type": "sim", "sim_number": "081234567890",
            "operator": "Telkomsel", "person_in_charge": "Budi",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(sim_response.status_code, 302)
        first_sim = InternetSimCard.objects.get(item=modem)
        self.assertEqual(first_sim.person_in_charge, "Budi")
        ready = self.client.get(url, HTTP_HOST="inventory.localhost")
        self.assertContains(ready, "Simpan Riwayat")
        self.assertIn("sim_card", ready.context["package_form"].fields)
        self.assertNotIn("sim_number", ready.context["package_form"].fields)
        self.assertNotIn("operator", ready.context["package_form"].fields)
        self.assertNotIn("person_in_charge", ready.context["package_form"].fields)

        today = timezone.localdate()
        first_start = today - timedelta(days=30)
        first_end = today - timedelta(days=1)
        first = self.client.post(url, {
            "form_type": "package", "sim_card": first_sim.pk,
            "package_name": "Paket 50 GB", "effective_on": first_start.isoformat(),
            "expires_on": first_end.isoformat(), "notes": "Paket awal",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(first.status_code, 302)
        self.assertEqual(InternetPackageHistory.objects.filter(item=modem).count(), 1)
        prefilled = self.client.get(url, HTTP_HOST="inventory.localhost")
        self.assertContains(prefilled, f'value="{first_sim.pk}" selected')
        self.assertContains(prefilled, "Lewat batas berlaku")

        second_sim_response = self.client.post(url, {
            "form_type": "sim", "sim_number": "089876543210",
            "operator": "XL", "person_in_charge": "Sari",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(second_sim_response.status_code, 302)
        second_sim = InternetSimCard.objects.get(item=modem, sim_number="089876543210")
        renewal = self.client.post(url, {
            "form_type": "package", "sim_card": second_sim.pk,
            "package_name": "Paket 100 GB", "effective_on": today.isoformat(),
            "expires_on": (today + timedelta(days=30)).isoformat(),
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(renewal.status_code, 302)
        detail = self.client.get(url, HTTP_HOST="inventory.localhost")
        self.assertEqual(detail.context["current"].package_name, "Paket 100 GB")
        self.assertEqual(detail.context["current"].sim_card_id, second_sim.pk)
        self.assertContains(detail, "081234567890")
        self.assertContains(detail, "089876543210")
        self.assertContains(detail, "Paket awal")
        self.assertEqual(len(detail.context["history"]), 2)
        listing = self.client.get(reverse("inventory:internet_list"), HTTP_HOST="inventory.localhost")
        self.assertContains(listing, "Paket 100 GB")
        self.assertContains(listing, "089876543210")
        self.assertContains(listing, url)

        other_modem = InventoryItem.objects.create(
            asset_code="MODEM-OTHER-1", item_name="Modem Lain", category="modem_wifi",
            created_by=self.manager, updated_by=self.manager,
        )
        other_sim = InternetSimCard.objects.create(
            item=other_modem, sim_number="080000000000", created_by=it_user,
        )
        wrong_sim = self.client.post(url, {
            "form_type": "package", "sim_card": other_sim.pk,
            "package_name": "Paket Salah", "effective_on": today.isoformat(),
            "expires_on": (today + timedelta(days=30)).isoformat(),
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(wrong_sim.status_code, 200)
        self.assertIn("sim_card", wrong_sim.context["package_form"].errors)
        invalid = self.client.post(url, {
            "form_type": "package", "sim_card": first_sim.pk,
            "package_name": "Tanggal Salah", "effective_on": today.isoformat(),
            "expires_on": (today - timedelta(days=1)).isoformat(),
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(invalid.status_code, 200)
        self.assertIn("expires_on", invalid.context["package_form"].errors)
        self.assertEqual(InternetPackageHistory.objects.filter(item=modem).count(), 2)

        self.client.force_login(self.superuser)
        self.assertEqual(
            self.client.get(reverse("inventory:internet_detail", args=[self.item.pk]), HTTP_HOST="inventory.localhost").status_code,
            404,
        )
        delete = self.client.post(
            reverse("inventory:item_delete", args=[modem.pk]), HTTP_HOST="inventory.localhost"
        )
        self.assertEqual(delete.status_code, 302)
        self.assertTrue(InventoryItem.objects.filter(pk=modem.pk).exists())

    def test_existing_package_sim_details_are_moved_to_cards(self):
        modem = InventoryItem.objects.create(
            asset_code="MODEM-LEGACY-1", item_name="Router Modem Lama",
            category="modem_wifi", created_by=self.manager, updated_by=self.manager,
        )
        today = timezone.localdate()
        legacy = InternetPackageHistory.objects.create(
            item=modem, sim_number="081111111111", operator="Telkomsel",
            person_in_charge="Budi", package_name="Paket Lama",
            effective_on=today, expires_on=today + timedelta(days=30),
            created_by=self.manager,
        )
        migration = import_module("inventory.migrations.0017_separate_internet_sim_cards")
        migration.move_sim_details_to_cards(apps, SimpleNamespace(connection=connection))
        legacy.refresh_from_db()
        self.assertEqual(legacy.sim_card.sim_number, "081111111111")
        self.assertEqual(legacy.sim_card.operator, "Telkomsel")
        self.assertEqual(legacy.sim_card.person_in_charge, "Budi")
        self.assertEqual(legacy.sim_number, "081111111111")

    def test_software_account_fields_are_optional_and_password_is_protected(self):
        self.client.force_login(self.manager)
        create_url = reverse("inventory:item_create")
        form_page = self.client.get(f"{create_url}?category=software", HTTP_HOST="inventory.localhost")
        self.assertContains(form_page, 'data-software-only')
        self.assertContains(form_page, 'data-physical-only hidden')
        self.assertContains(form_page, 'name="software_password"')
        response = self.client.post(create_url, {
            "item_name": "Aplikasi Kantor", "category": "software",
            "software_username": "pegawai-1", "software_email": "pegawai@example.com",
            "software_password": "secret-value-123", "location": "Ruang SPI",
            "condition": "damaged",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item = InventoryItem.objects.get(item_name="Aplikasi Kantor")
        self.assertEqual(item.software_username, "pegawai-1")
        self.assertEqual(item.software_email, "pegawai@example.com")
        self.assertNotIn("secret-value-123", item.software_password_encrypted)
        self.assertEqual(decrypt_software_password(item.software_password_encrypted), "secret-value-123")
        with override_settings(
            SECRET_KEY="rotated-test-key", SECRET_KEY_FALLBACKS=[settings.SECRET_KEY]
        ):
            self.assertEqual(
                decrypt_software_password(item.software_password_encrypted), "secret-value-123"
            )
        self.assertEqual(item.location, "")
        self.assertEqual(item.condition, "good")
        self.assertFalse(item.photo)

        detail = self.client.get(reverse("inventory:item_detail", args=[item.pk]), HTTP_HOST="inventory.localhost")
        self.assertContains(detail, "pegawai@example.com")
        self.assertNotContains(detail, "secret-value-123")
        self.assertNotContains(detail, ">Lokasi</dt>")
        self.assertNotContains(detail, ">Kondisi</dt>")
        password_url = reverse("inventory:software_password_reveal", args=[item.pk])
        self.assertEqual(self.client.get(password_url, HTTP_HOST="inventory.localhost").status_code, 405)
        revealed = self.client.post(password_url, HTTP_HOST="inventory.localhost")
        self.assertEqual(revealed.status_code, 200)
        self.assertEqual(revealed.json()["password"], "secret-value-123")
        self.assertIn("no-store", revealed["Cache-Control"])

        export = self.client.get(reverse("inventory:export_inventory_excel"), HTTP_HOST="inventory.localhost")
        workbook = load_workbook(BytesIO(export.content), read_only=True)
        rows = list(workbook["Daftar Inventaris"].iter_rows(min_row=6, values_only=True))
        software_row = next(row for row in rows if row[1] == "Aplikasi Kantor")
        self.assertIsNone(software_row[12])
        self.assertIsNone(software_row[20])
        self.assertNotIn("secret-value-123", str(rows))

        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(password_url, HTTP_HOST="inventory.localhost").status_code, 403)

    def test_software_billing_fields_work_for_manager_and_personal_inventory(self):
        self.client.force_login(self.manager)
        create_url = reverse("inventory:item_create")
        form_page = self.client.get(f"{create_url}?category=software", HTTP_HOST="inventory.localhost")
        self.assertContains(form_page, "Nama Software")
        self.assertContains(form_page, "Developer / Distributor")
        self.assertContains(form_page, 'name="software_payment_method"')
        response = self.client.post(create_url, {
            "item_name": "Office Suite", "category": "software", "brand": "Vendor A",
            "purchase_price": "150000", "software_billing_type": "subscription",
            "software_billing_cycle": "monthly", "software_payment_method": "Transfer bank",
            "software_renewal_date": "2026-12-02",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        software = InventoryItem.objects.get(item_name="Office Suite")
        self.assertEqual(software.brand, "Vendor A")
        self.assertEqual(software.purchase_price, Decimal("150000"))
        self.assertEqual(software.software_billing_cycle, "monthly")
        detail = self.client.get(reverse("inventory:item_detail", args=[software.pk]), HTTP_HOST="inventory.localhost")
        self.assertContains(detail, "Transfer bank")
        self.assertContains(detail, "Biaya &amp; Pembayaran Software")

        edit_url = reverse("inventory:item_edit", args=[software.pk])
        response = self.client.post(edit_url, {
            "item_name": "Office Suite", "category": "software",
            "software_billing_type": "one_time", "software_billing_cycle": "monthly",
            "software_renewal_date": "2026-12-02", "software_payment_method": "Kartu kredit",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        software.refresh_from_db()
        self.assertEqual(software.software_billing_cycle, "")
        self.assertIsNone(software.software_renewal_date)
        self.assertEqual(software.software_payment_method, "Kartu kredit")

        self.client.force_login(self.viewer)
        personal_url = reverse("inventory:personal_item_create")
        page = self.client.get(f"{personal_url}?category=software", HTTP_HOST="inventory.localhost")
        self.assertContains(page, 'name="purchase_price"')
        response = self.client.post(personal_url, {
            "item_name": "Design App", "category": "software", "purchase_price": "900000",
            "software_billing_type": "subscription", "software_billing_cycle": "yearly",
            "software_payment_method": "Kartu perusahaan",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        personal = InventoryItem.objects.get(item_name="Design App")
        self.assertEqual(personal.purchase_price, Decimal("900000"))
        self.assertEqual(personal.software_billing_cycle, "yearly")

    def test_personal_software_password_can_be_kept_and_cleared(self):
        self.client.force_login(self.viewer)
        create_url = reverse("inventory:personal_item_create")
        form_page = self.client.get(f"{create_url}?category=software", HTTP_HOST="inventory.localhost")
        self.assertContains(form_page, 'data-software-only')
        self.assertContains(form_page, 'data-physical-only hidden')
        response = self.client.post(create_url, {
            "item_name": "Software Pribadi", "category": "software",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item = InventoryItem.objects.get(item_name="Software Pribadi")
        self.assertIsNone(item.software_username)
        self.assertIsNone(item.software_email)
        self.assertIsNone(item.software_password_encrypted)

        edit_url = reverse("inventory:personal_item_edit", args=[item.pk])
        response = self.client.post(edit_url, {
            "item_name": "Software Pribadi", "category": "software",
            "software_username": "akun-pribadi", "software_password": "private-password",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        ciphertext = item.software_password_encrypted
        self.assertEqual(decrypt_software_password(ciphertext), "private-password")
        password_url = reverse("inventory:software_password_reveal", args=[item.pk])
        self.assertEqual(
            self.client.post(password_url, HTTP_HOST="inventory.localhost").json()["password"],
            "private-password",
        )

        response = self.client.post(edit_url, {
            "item_name": "Software Pribadi", "category": "software",
            "software_username": "akun-pribadi",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.software_password_encrypted, ciphertext)

        response = self.client.post(edit_url, {
            "item_name": "Software Pribadi", "category": "software",
            "software_password_clear": "on",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertIsNone(item.software_password_encrypted)

        response = self.client.post(edit_url, {
            "item_name": "Perangkat Pribadi", "item_type": "hardware", "category": "hardware",
            "software_username": "tidak-disimpan",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertIsNone(item.software_username)
        self.assertIsNone(item.software_email)
        self.assertIsNone(item.software_password_encrypted)

    def test_room_options_are_saved_for_manager_and_personal_items(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("inventory:item_create"), HTTP_HOST="inventory.localhost")
        self.assertContains(response, "Ruang Umum &amp; Legal")
        self.assertContains(response, "Ruang SPI")
        self.assertContains(response, "Ruang Direktur Utama")
        self.assertContains(response, 'data-location-field')
        self.assertContains(response, 'aria-describedby="inventory-location-help"')
        locations = [value for value, _label in response.context["form"].fields["location"].choices][1:]
        self.assertEqual(locations, sorted(locations, key=str.casefold))
        self.assertNotIn("Ruang Umum", locations)
        for location in (
            "Pos", "Garasi", "Rumah Ketiga", "Hall", "Dapur", "Gudang",
            "Ruang Komisaris", "Musholla", "Ruang Rapat",
        ):
            self.assertIn(location, locations)
        response = self.client.post(reverse("inventory:item_create"), {
            "item_name": "Meja Akuntansi", "category": "office",
            "location": "Ruang Akuntansi",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InventoryItem.objects.get(item_name="Meja Akuntansi").location, "Ruang Akuntansi")

        self.client.force_login(self.viewer)
        personal_form = self.client.get(
            reverse("inventory:personal_item_create"), HTTP_HOST="inventory.localhost"
        )
        self.assertContains(personal_form, 'data-location-field')
        response = self.client.post(reverse("inventory:personal_item_create"), {
            "item_name": "Mouse SPI", "category": "peripheral",
            "location": "Ruang SPI",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InventoryItem.objects.get(item_name="Mouse SPI").location, "Ruang SPI")

    def test_existing_custom_location_remains_editable(self):
        self.item.location = "Gudang Lantai 2"
        self.item.save(update_fields=["location"])
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse("inventory:item_edit", args=[self.item.pk]), HTTP_HOST="inventory.localhost"
        )
        self.assertContains(response, 'value="Gudang Lantai 2" selected')

    def test_manager_can_sync_purchase_and_received_dates(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("inventory:item_edit", args=[self.item.pk]), {
            "item_name": "Laptop", "category": "hardware", "ownership": "company",
            "status": "assigned", "assigned_to": self.member.pk,
            "purchase_date": "2026-01-05", "received_date": "2026-01-20",
            "received_date_same_as_purchase": "on",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.purchase_date.isoformat(), "2026-01-05")
        self.assertEqual(self.item.received_date, self.item.purchase_date)
        self.assertTrue(self.item.received_date_same_as_purchase)
        edit_page = self.client.get(reverse("inventory:item_edit", args=[self.item.pk]), HTTP_HOST="inventory.localhost")
        self.assertContains(edit_page, 'name="received_date_same_as_purchase"')
        self.assertContains(edit_page, 'checked')

        response = self.client.post(reverse("inventory:item_edit", args=[self.item.pk]), {
            "item_name": "Laptop", "category": "hardware", "ownership": "company",
            "status": "assigned", "assigned_to": self.member.pk,
            "purchase_date": "2026-01-05", "received_date": "2026-01-10",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.received_date.isoformat(), "2026-01-10")
        self.assertFalse(self.item.received_date_same_as_purchase)

    def test_sync_date_requires_purchase_date(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("inventory:item_create"), {
            "item_name": "Keyboard Baru", "category": "peripheral",
            "received_date_same_as_purchase": "on",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertIn("purchase_date", response.context["form"].errors)
        self.assertFalse(InventoryItem.objects.filter(item_name="Keyboard Baru").exists())

    def test_unknown_purchase_date_keeps_received_date_independent(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("inventory:item_create"), {
            "item_name": "Keyboard Tanpa Tanggal Beli", "category": "peripheral",
            "purchase_date": "2026-01-05", "purchase_date_unknown": "on",
            "received_date": "2026-01-20", "received_date_same_as_purchase": "on",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item = InventoryItem.objects.get(item_name="Keyboard Tanpa Tanggal Beli")
        self.assertIsNone(item.purchase_date)
        self.assertTrue(item.purchase_date_unknown)
        self.assertFalse(item.received_date_same_as_purchase)
        self.assertEqual(item.received_date.isoformat(), "2026-01-20")
        edit_page = self.client.get(
            reverse("inventory:item_edit", args=[item.pk]), HTTP_HOST="inventory.localhost"
        )
        self.assertContains(edit_page, 'name="purchase_date_unknown"')
        self.assertContains(edit_page, "Tanggal pembelian tidak diketahui")

    def test_personal_item_can_mark_purchase_date_unknown(self):
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("inventory:personal_item_create"), {
            "item_name": "Mouse Tanpa Tanggal Beli", "category": "peripheral",
            "purchase_date_unknown": "on", "received_date": "2026-02-14",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item = InventoryItem.objects.get(item_name="Mouse Tanpa Tanggal Beli")
        self.assertTrue(item.purchase_date_unknown)
        self.assertIsNone(item.purchase_date)
        self.assertEqual(item.received_date.isoformat(), "2026-02-14")
        edit_page = self.client.get(
            reverse("inventory:personal_item_edit", args=[item.pk]),
            HTTP_HOST="inventory.localhost",
        )
        self.assertContains(edit_page, "Tanggal pembelian tidak diketahui")

    def test_existing_item_codes_follow_ownership_migration(self):
        lumbung = InventoryItem.objects.create(
            asset_code="PRIBADI-ABC123", item_name="Keyboard Lumbung",
            category="peripheral", ownership="lumbung",
            created_by=self.viewer, updated_by=self.viewer,
        )
        personal = InventoryItem.objects.create(
            asset_code="INV-XYZ987", item_name="Mouse Pribadi",
            category="peripheral", ownership="personal",
            created_by=self.viewer, updated_by=self.viewer,
        )
        migration = import_module("inventory.migrations.0011_ownership_asset_codes")
        migration.update_asset_codes(apps, None)
        self.item.refresh_from_db()
        lumbung.refresh_from_db()
        personal.refresh_from_db()
        self.assertEqual(self.item.asset_code, "COMPANY-AST-001")
        self.assertEqual(lumbung.asset_code, "LUMBUNG-ABC123")
        self.assertEqual(personal.asset_code, "PERSONAL-XYZ987")

    def test_manager_code_uses_selected_ownership_and_can_delete_item(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("inventory:item_create"), {
            "item_name": "Keyboard Perusahaan", "category": "peripheral",
            "ownership": "company", "asset_code": "KEY-001",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item = InventoryItem.objects.get(item_name="Keyboard Perusahaan")
        self.assertEqual(item.asset_code, "COMPANY-KEY-001")
        response = self.client.post(reverse("inventory:item_edit", args=[item.pk]), {
            "item_name": item.item_name, "category": "peripheral",
            "ownership": "lumbung", "asset_code": item.asset_code,
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.asset_code, "LUMBUNG-KEY-001")
        response = self.client.post(reverse("inventory:item_delete", args=[item.pk]), HTTP_HOST="inventory.localhost")
        self.assertRedirects(response, reverse("inventory:item_list"), fetch_redirect_response=False)
        self.assertFalse(InventoryItem.objects.filter(pk=item.pk).exists())

    def test_third_party_ownership_requires_name_and_displays_it(self):
        self.client.force_login(self.manager)
        url = reverse("inventory:item_create")
        response = self.client.post(url, {
            "item_name": "Printer Pinjaman", "category": "office",
            "ownership": "third_party", "third_party_name": "   ",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertIn("third_party_name", response.context["form"].errors)
        self.assertFalse(InventoryItem.objects.filter(item_name="Printer Pinjaman").exists())

        response = self.client.post(url, {
            "item_name": "Printer Pinjaman", "category": "office",
            "ownership": "third_party", "third_party_name": "  PT Mitra  ",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item = InventoryItem.objects.get(item_name="Printer Pinjaman")
        self.assertEqual(item.ownership, "third_party")
        self.assertEqual(item.third_party_name, "PT Mitra")
        detail = self.client.get(reverse("inventory:item_detail", args=[item.pk]), HTTP_HOST="inventory.localhost")
        self.assertContains(detail, "Kepemilikan")
        self.assertContains(detail, "PT Mitra")
        for route in ("dashboard", "item_list"):
            listing = self.client.get(reverse(f"inventory:{route}"), {
                "ownership": "third_party", "q": "PT Mitra",
            }, HTTP_HOST="inventory.localhost")
            self.assertEqual([entry.pk for entry in listing.context["page_obj"]], [item.pk])

        response = self.client.post(reverse("inventory:item_edit", args=[item.pk]), {
            "item_name": "Printer Pinjaman", "category": "office",
            "ownership": "lumbung", "third_party_name": "PT Mitra",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.ownership, "lumbung")
        self.assertEqual(item.third_party_name, "")

    def test_personal_inventory_defaults_to_personal_ownership(self):
        self.client.force_login(self.viewer)
        form_page = self.client.get(reverse("inventory:personal_item_create"), HTTP_HOST="inventory.localhost")
        self.assertContains(form_page, 'name="ownership"')
        self.assertContains(form_page, 'value="personal" selected')
        self.assertContains(form_page, 'name="third_party_name"')
        response = self.client.post(reverse("inventory:personal_item_create"), {
            "item_name": "Mouse Pribadi", "category": "peripheral",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item = InventoryItem.objects.get(item_name="Mouse Pribadi")
        self.assertEqual(item.ownership, "personal")

        response = self.client.post(reverse("inventory:personal_item_create"), {
            "item_name": "Monitor Titipan", "category": "peripheral",
            "ownership": "third_party",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertIn("third_party_name", response.context["form"].errors)

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

    def test_excel_report_downloads_all_inventory_with_summary_and_safe_text(self):
        InventoryItem.objects.create(
            asset_code="LUMBUNG-MON-002", item_name="Monitor", category="peripheral",
            ownership="lumbung", purchase_date_unknown=True,
            received_date="2026-03-18", purchase_price=Decimal("2000000"),
            quantity=2, condition="good", status="stock",
            notes="=SUM(1,2)", created_by=self.manager, updated_by=self.manager,
        )
        self.client.force_login(self.manager)
        export_url = reverse("inventory:export_inventory_excel")
        for route in ("dashboard", "item_list"):
            page = self.client.get(reverse(f"inventory:{route}"), HTTP_HOST="inventory.localhost")
            self.assertContains(page, export_url)
            self.assertContains(page, "Unduh Laporan Excel")

        response = self.client.get(export_url, {"q": "tidak-ada"}, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])
        self.assertIn(".xlsx", response["Content-Disposition"])
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        workbook = load_workbook(BytesIO(response.content), read_only=True)
        self.assertEqual(workbook.sheetnames, ["Ringkasan", "Daftar Inventaris"])
        self.assertEqual(workbook["Ringkasan"]["A6"].value, 2)
        self.assertEqual(workbook["Ringkasan"]["C6"].value, 3)
        sheet = workbook["Daftar Inventaris"]
        self.assertEqual(sheet["A5"].value, "Kode Aset")
        self.assertEqual(sheet["H5"].value, "Tanggal Pembelian")
        rows = list(sheet.iter_rows(min_row=6, values_only=True))
        self.assertEqual(len(rows), 2)
        self.assertIn("AST-001", [row[0] for row in rows])
        monitor = next(row for row in rows if row[1] == "Monitor")
        self.assertEqual(monitor[9], "Tidak diketahui")
        self.assertEqual(monitor[21], "'=SUM(1,2)")

    def test_participant_cannot_download_all_inventory(self):
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse("inventory:export_inventory_excel"),
            HTTP_HOST="inventory.localhost",
        )
        self.assertEqual(response.status_code, 403)

    def test_dashboard_filters_items_and_summary_and_sorts_results(self):
        InventoryItem.objects.create(
            asset_code="AST-002", item_name="Monitor", category="peripheral",
            serial_number="MON-123", purchase_price=Decimal("2000000"),
            quantity=3, condition="damaged", status="maintenance",
            created_by=self.manager, updated_by=self.manager,
        )
        self.client.force_login(self.manager)
        url = reverse("inventory:dashboard")

        response = self.client.get(url, {
            "q": "MON-123", "category": "peripheral", "status": "maintenance",
            "condition": "damaged", "sort": "quantity_desc",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual([item.asset_code for item in response.context["page_obj"]], ["AST-002"])
        self.assertEqual(response.context["item_count"], 3)
        self.assertEqual(response.context["assigned_count"], 0)
        self.assertEqual(response.context["maintenance_count"], 1)
        self.assertEqual(response.context["total_value"], Decimal("6000000"))
        self.assertContains(response, 'value="quantity_desc" selected')

        response = self.client.get(url, {"sort": "name_desc"}, HTTP_HOST="inventory.localhost")
        self.assertEqual(
            [item.item_name for item in response.context["page_obj"]],
            ["Monitor", "Laptop"],
        )

    def test_dashboard_pagination_keeps_filters_and_sort(self):
        for number in range(21):
            InventoryItem.objects.create(
                asset_code=f"MON-{number:02d}", item_name=f"Monitor {number:02d}",
                category="peripheral", status="stock",
                created_by=self.manager, updated_by=self.manager,
            )
        self.client.force_login(self.manager)
        response = self.client.get(reverse("inventory:dashboard"), {
            "category": "peripheral", "sort": "code_asc",
        }, HTTP_HOST="inventory.localhost")

        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertEqual(response.context["page_obj"].paginator.count, 21)
        self.assertContains(response, "category=peripheral&amp;sort=code_asc&amp;page=2")

        next_page = self.client.get(reverse("inventory:dashboard"), {
            "category": "peripheral", "sort": "code_asc", "page": "2",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual([item.asset_code for item in next_page.context["page_obj"]], ["MON-20"])

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
        self.assertContains(response, "Kembali ke Portal Utama")
        self.assertContains(response, ">Keluar<")
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

    def test_manager_can_advance_report_workflow(self):
        report = InventoryReport.objects.create(
            item=self.item,
            reporter=self.viewer,
            report_type="complaint",
            description="Perangkat lambat.",
        )
        self.client.force_login(self.manager)
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
        self.assertTrue(created_item.asset_code.startswith("PERSONAL-"))

    def test_personal_item_dates_follow_checkbox(self):
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("inventory:personal_item_create"), {
            "item_name": "Keyboard Tanggal", "category": "peripheral",
            "purchase_date": "2026-10-01", "received_date": "2026-10-11",
            "received_date_same_as_purchase": "on",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item = InventoryItem.objects.get(item_name="Keyboard Tanggal")
        self.assertEqual(item.received_date, item.purchase_date)
        self.assertTrue(item.received_date_same_as_purchase)
        response = self.client.post(reverse("inventory:personal_item_edit", args=[item.pk]), {
            "item_name": item.item_name, "category": "peripheral",
            "purchase_date": "2026-10-02", "received_date": "2026-10-20",
            "received_date_same_as_purchase": "on",
        }, HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.received_date.isoformat(), "2026-10-02")

    def test_participant_can_edit_self_added_item_only(self):
        self.client.force_login(self.viewer)
        self.client.post(reverse("inventory:personal_item_create"), {
            "item_name": "Mouse Saya", "category": "peripheral",
            "ownership": "personal",
        }, HTTP_HOST="inventory.localhost")
        item = InventoryItem.objects.get(item_name="Mouse Saya")
        edit_url = reverse("inventory:personal_item_edit", args=[item.pk])
        detail = self.client.get(reverse("inventory:item_detail", args=[item.pk]), HTTP_HOST="inventory.localhost")
        self.assertContains(detail, edit_url)
        edit_page = self.client.get(edit_url, HTTP_HOST="inventory.localhost")
        self.assertContains(edit_page, "Edit Inventaris Saya")
        self.assertNotIn("assigned_to", edit_page.context["form"].fields)
        self.assertNotIn("asset_code", edit_page.context["form"].fields)

        response = self.client.post(edit_url, {
            "item_name": "Mouse Saya Baru", "category": "peripheral",
            "brand": "Logitech", "ownership": "third_party",
            "third_party_name": "  PT Mitra  ",
            "asset_code": "FORGED", "assigned_to": self.manager.company_member_profile.pk,
            "status": "stock", "purchase_price": "999999",
        }, HTTP_HOST="inventory.localhost")
        self.assertRedirects(response, reverse("inventory:item_detail", args=[item.pk]), fetch_redirect_response=False)
        item.refresh_from_db()
        self.assertEqual(item.item_name, "Mouse Saya Baru")
        self.assertEqual(item.brand, "Logitech")
        self.assertEqual(item.ownership, "third_party")
        self.assertEqual(item.third_party_name, "PT Mitra")
        self.assertEqual(item.assigned_to, self.member)
        self.assertTrue(item.asset_code.startswith("THIRD-PARTY-"))
        self.assertEqual(item.status, "assigned")
        self.assertEqual(item.purchase_price, 0)
        self.assertEqual(item.updated_by, self.viewer)
        self.assertTrue(item.activities.filter(actor=self.viewer, action="updated").exists())

        managed_url = reverse("inventory:personal_item_edit", args=[self.item.pk])
        self.assertEqual(self.client.get(managed_url, HTTP_HOST="inventory.localhost").status_code, 403)
        self.assertEqual(self.client.post(managed_url, {"item_name": "Changed"}, HTTP_HOST="inventory.localhost").status_code, 403)
        managed_detail = self.client.get(reverse("inventory:item_detail", args=[self.item.pk]), HTTP_HOST="inventory.localhost")
        self.assertNotContains(managed_detail, managed_url)

    def test_participant_cannot_edit_another_users_self_added_item(self):
        self.client.force_login(self.viewer)
        self.client.post(reverse("inventory:personal_item_create"), {
            "item_name": "Own Item", "category": "office",
        }, HTTP_HOST="inventory.localhost")
        item = InventoryItem.objects.get(item_name="Own Item")
        other = get_user_model().objects.create_user(
            username="inv-other", password="test-pass-123", role="inventory",
        )
        InventoryAccess.objects.create(user=other, role="participant")
        self.client.force_login(other)
        url = reverse("inventory:personal_item_edit", args=[item.pk])
        self.assertEqual(self.client.get(url, HTTP_HOST="inventory.localhost").status_code, 403)
        self.assertEqual(self.client.post(url, {"item_name": "Stolen"}, HTTP_HOST="inventory.localhost").status_code, 403)
        item.refresh_from_db()
        self.assertEqual(item.item_name, "Own Item")

    def test_self_added_code_follows_ownership_on_create_and_edit(self):
        self.client.force_login(self.viewer)
        for ownership, prefix in (("company", "COMPANY-"), ("lumbung", "LUMBUNG-"), ("personal", "PERSONAL-")):
            with self.subTest(ownership=ownership):
                name = f"Keyboard {ownership}"
                response = self.client.post(reverse("inventory:personal_item_create"), {
                    "item_name": name, "category": "peripheral", "ownership": ownership,
                }, HTTP_HOST="inventory.localhost")
                self.assertEqual(response.status_code, 302)
                item = InventoryItem.objects.get(item_name=name)
                self.assertTrue(item.asset_code.startswith(prefix))
                edit_url = reverse("inventory:personal_item_edit", args=[item.pk])
                self.assertEqual(self.client.get(edit_url, HTTP_HOST="inventory.localhost").status_code, 200)
                response = self.client.post(edit_url, {
                    "item_name": name, "category": "peripheral", "ownership": "personal",
                }, HTTP_HOST="inventory.localhost")
                self.assertEqual(response.status_code, 302)
                item.refresh_from_db()
                self.assertTrue(item.asset_code.startswith("PERSONAL-"))

    def test_self_added_item_can_be_deleted_from_edit_page(self):
        self.client.force_login(self.viewer)
        self.client.post(reverse("inventory:personal_item_create"), {
            "item_name": "Mouse Hapus", "category": "peripheral", "ownership": "company",
        }, HTTP_HOST="inventory.localhost")
        item = InventoryItem.objects.get(item_name="Mouse Hapus")
        delete_url = reverse("inventory:personal_item_delete", args=[item.pk])
        edit_page = self.client.get(reverse("inventory:personal_item_edit", args=[item.pk]), HTTP_HOST="inventory.localhost")
        self.assertContains(edit_page, delete_url)
        self.assertEqual(self.client.get(delete_url, HTTP_HOST="inventory.localhost").status_code, 200)
        response = self.client.post(delete_url, HTTP_HOST="inventory.localhost")
        self.assertRedirects(response, reverse("inventory:member_detail", args=[self.member.pk]), fetch_redirect_response=False)
        self.assertFalse(InventoryItem.objects.filter(pk=item.pk).exists())

    def test_other_user_cannot_delete_self_added_item(self):
        self.client.force_login(self.viewer)
        self.client.post(reverse("inventory:personal_item_create"), {
            "item_name": "Mouse Aman", "category": "peripheral",
        }, HTTP_HOST="inventory.localhost")
        item = InventoryItem.objects.get(item_name="Mouse Aman")
        self.client.force_login(self.manager)
        response = self.client.post(reverse("inventory:personal_item_delete", args=[item.pk]), HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(InventoryItem.objects.filter(pk=item.pk).exists())

    def test_item_with_report_keeps_its_history(self):
        InventoryReport.objects.create(
            item=self.item, reporter=self.viewer, report_type="damaged",
            description="Perlu diperbaiki.",
        )
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("inventory:item_delete", args=[self.item.pk]),
            HTTP_HOST="inventory.localhost",
        )
        self.assertRedirects(
            response, reverse("inventory:item_detail", args=[self.item.pk]),
            fetch_redirect_response=False,
        )
        self.assertTrue(InventoryItem.objects.filter(pk=self.item.pk).exists())

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
                self.assertEqual(response.context["form"].fields["item_type"].initial, category_section(section))
        self.assertFalse(InventoryItem.objects.filter(item_name="Invalid").exists())

    def test_minimal_item_and_optional_date(self):
        for user, route in ((self.viewer, "personal_item_create"), (self.manager, "item_create")):
            self.client.force_login(user)
            url = reverse(f"inventory:{route}") + "?category=office"
            response = self.client.get(url, HTTP_HOST="inventory.localhost")
            self.assertIn("serial_number", response.context["form"].fields)
            self.assertContains(response, 'name="item_type"')
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

    def test_item_type_can_change_on_create_and_edit(self):
        for user, create_route, edit_route in (
            (self.viewer, "personal_item_create", "personal_item_edit"),
            (self.manager, "item_create", "item_edit"),
        ):
            self.client.force_login(user)
            create_url = reverse(f"inventory:{create_route}") + "?category=office"
            page = self.client.get(create_url, HTTP_HOST="inventory.localhost")
            self.assertContains(page, 'name="item_type"')
            self.assertContains(page, ">Hardware</option>")
            response = self.client.post(create_url, {
                "item_name": f"Type Test {create_route}",
                "item_type": "hardware", "category": "laptop",
                "serial_number": "HW-001",
            }, HTTP_HOST="inventory.localhost")
            self.assertEqual(response.status_code, 302)
            item = InventoryItem.objects.get(item_name=f"Type Test {create_route}")
            self.assertEqual(item.category, "laptop")
            self.assertEqual(item.serial_number, "HW-001")

            edit_url = reverse(f"inventory:{edit_route}", args=[item.pk])
            response = self.client.post(edit_url, {
                "item_name": item.item_name, "item_type": "software",
                "category": "software", "serial_number": "LIC-001",
            }, HTTP_HOST="inventory.localhost")
            self.assertEqual(response.status_code, 302)
            item.refresh_from_db()
            self.assertEqual(item.category, "software")
            self.assertEqual(item.serial_number, "LIC-001")

            invalid = self.client.post(edit_url, {
                "item_name": item.item_name, "item_type": "hardware", "category": "software",
            }, HTTP_HOST="inventory.localhost")
            self.assertEqual(invalid.status_code, 200)
            self.assertIn("category", invalid.context["form"].errors)

            response = self.client.post(edit_url, {
                "item_name": item.item_name, "item_type": "inventaris",
                "category": "office", "serial_number": "SHOULD-CLEAR",
            }, HTTP_HOST="inventory.localhost")
            self.assertEqual(response.status_code, 302)
            item.refresh_from_db()
            self.assertEqual(item.category, "office")
            self.assertEqual(item.serial_number, "")

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
