from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CompanyMember, InventoryAccess, InventoryItem


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}, ROOT_URLCONF="inventory.host_urls")
class InventoryPermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username="inv-manager", password="test-pass-123", role="inventory")
        self.viewer = User.objects.create_user(username="inv-viewer", password="test-pass-123", role="inventory")
        InventoryAccess.objects.create(user=self.manager, role="manager")
        InventoryAccess.objects.create(user=self.viewer, role="participant")
        self.member = CompanyMember.objects.create(employee_id="EMP-001", full_name="Budi", division="TI", position="Staff")
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

    def test_participant_is_read_only(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("inventory:item_edit", args=[self.item.pk]), HTTP_HOST="inventory.localhost")
        self.assertEqual(response.status_code, 403)

    def test_member_detail_lists_assigned_item(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("inventory:member_detail", args=[self.member.pk]), HTTP_HOST="inventory.localhost")
        self.assertContains(response, "AST-001")

    def test_total_value(self):
        self.assertEqual(self.item.total_value, Decimal("12000000"))
