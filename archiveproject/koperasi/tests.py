from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .forms import SavingTransactionForm
from .models import (
    Company,
    KoperasiAccess,
    Loan,
    LoanInstallment,
    Member,
    SavingTransaction,
)


HOST_SETTINGS = override_settings(
    ALLOWED_HOSTS=[
        "testserver",
        "koperasi.localhost",
        "archive.localhost",
        "localhost",
    ],
    KOPERASI_HOSTS=frozenset({"koperasi.localhost"}),
    LANDING_HOSTS=frozenset({"localhost"}),
)


@HOST_SETTINGS
class KoperasiHostTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="it_pwu",
            password="test-password",
            role="admin",
        )

    def test_koperasi_host_requires_login(self):
        response = self.client.get("/", HTTP_HOST="koperasi.localhost:8000")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_it_user_can_open_koperasi_dashboard(self):
        self.client.force_login(self.user)

        response = self.client.get("/", HTTP_HOST="koperasi.localhost:8000")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ringkasan Koperasi Grup")
        self.assertContains(response, "SISTEM KOPERASI PWU")

    def test_koperasi_login_uses_koperasi_branding(self):
        response = self.client.get(
            "/accounts/login/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sistem Koperasi PWU")

    def test_archive_role_cannot_log_in_to_koperasi(self):
        archive_user = get_user_model().objects.create_user(
            username="archive_user",
            password="test-password",
            role="sekretaris",
        )

        response = self.client.post(
            "/accounts/login/",
            {
                "username": archive_user.username,
                "password": "test-password",
            },
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "tidak memiliki akses ke Sistem Koperasi",
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_accountant_without_scope_assignment_can_open_dashboard(self):
        accountant = get_user_model().objects.create_user(
            username="akuntan_grup",
            password="test-password",
            role="akuntan",
        )
        self.client.force_login(accountant)

        response = self.client.get("/", HTTP_HOST="koperasi.localhost:8000")

        self.assertEqual(response.status_code, 200)


@HOST_SETTINGS
class KoperasiScopeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="koperasi_petugas",
            password="test-password",
            role="akuntan",
        )
        self.company_a = Company.objects.create(code="A", name="Company A")
        self.company_b = Company.objects.create(code="B", name="Company B")
        KoperasiAccess.objects.create(
            user=self.user,
            company=self.company_a,
            role="officer",
        )
        self.member_a = Member.objects.create(
            member_number="A-001",
            company=self.company_a,
            full_name="Anggota A",
            join_date=date.today(),
        )
        Member.objects.create(
            member_number="B-001",
            company=self.company_b,
            full_name="Anggota B",
            join_date=date.today(),
        )
        self.client.force_login(self.user)

    def test_user_only_sees_assigned_company_members(self):
        response = self.client.get(
            "/anggota/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertContains(response, "Anggota A")
        self.assertNotContains(response, "Anggota B")

    def test_withdrawal_cannot_exceed_saving_balance(self):
        SavingTransaction.objects.create(
            transaction_number="S-001",
            member=self.member_a,
            saving_type="voluntary",
            direction="deposit",
            transaction_date=date.today(),
            amount=Decimal("100000"),
            created_by=self.user,
        )
        form = SavingTransactionForm(
            data={
                "transaction_number": "S-002",
                "member": self.member_a.pk,
                "saving_type": "voluntary",
                "direction": "withdrawal",
                "transaction_date": date.today(),
                "amount": "150000",
                "reference": "",
                "notes": "",
            },
            members=Member.objects.all(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("melebihi saldo", str(form.non_field_errors()))

    def test_user_without_koperasi_access_is_forbidden(self):
        other = get_user_model().objects.create_user(
            username="archive_only",
            password="test-password",
            role="sekretaris",
        )
        KoperasiAccess.objects.create(
            user=other,
            company=None,
            role="admin",
        )
        self.client.force_login(other)

        response = self.client.get("/", HTTP_HOST="koperasi.localhost:8000")

        self.assertEqual(response.status_code, 403)

    def test_scoped_officer_cannot_manage_global_access(self):
        response = self.client.get(
            "/akses/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 403)

    def test_accountant_is_redirected_away_from_archive(self):
        response = self.client.get(
            "/",
            HTTP_HOST="archive.localhost:8000",
        )

        self.assertRedirects(
            response,
            "http://koperasi.localhost:8000/",
            fetch_redirect_response=False,
        )

    def test_accountant_cannot_log_in_to_archive(self):
        self.client.logout()

        response = self.client.post(
            "/accounts/login/",
            {
                "username": self.user.username,
                "password": "test-password",
            },
            HTTP_HOST="archive.localhost:8000",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hanya dapat digunakan")
        self.assertNotIn("_auth_user_id", self.client.session)


@HOST_SETTINGS
class LoanWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="koperasi_manager",
            password="test-password",
            role="akuntan",
        )
        self.company = Company.objects.create(code="PWU", name="PWU")
        KoperasiAccess.objects.create(
            user=self.user,
            company=None,
            role="manager",
        )
        self.member = Member.objects.create(
            member_number="PWU-001",
            company=self.company,
            full_name="Anggota Uji",
            join_date=date.today(),
        )
        self.loan = Loan.objects.create(
            loan_number="P-001",
            member=self.member,
            application_date=date.today(),
            principal_amount=Decimal("1200000"),
            interest_rate=Decimal("12"),
            term_months=12,
            purpose="Uji pinjaman",
            status="active",
            created_by=self.user,
        )

    def test_loan_calculates_interest_and_outstanding(self):
        self.assertEqual(self.loan.total_interest, Decimal("144000.00"))
        self.assertEqual(self.loan.total_due, Decimal("1344000.00"))
        self.assertEqual(self.loan.outstanding_amount, Decimal("1344000.00"))

    def test_full_installment_marks_loan_paid(self):
        self.client.force_login(self.user)
        response = self.client.post(
            f"/pinjaman/{self.loan.pk}/angsuran/",
            {
                "payment_number": "PAY-001",
                "payment_date": date.today(),
                "principal_amount": "1200000",
                "interest_amount": "144000",
                "penalty_amount": "0",
                "reference": "",
                "notes": "",
            },
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 302)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.status, "paid")
        self.assertEqual(LoanInstallment.objects.count(), 1)
