from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from inventory.models import InventoryAccess
from koperasi.models import KoperasiAccess
from risk_management.models import RiskAccess


class SharedSystemAccessTests(TransactionTestCase):
    def test_new_user_receives_baseline_access_to_every_system(self):
        user = get_user_model().objects.create_user(
            username="shared_employee",
            password="safe-test-password",
            role="employee",
        )
        self.assertFalse(KoperasiAccess.objects.filter(user=user).exists())
        self.assertFalse(RiskAccess.objects.filter(user=user).exists())
        self.assertTrue(InventoryAccess.objects.filter(user=user, role="participant").exists())
