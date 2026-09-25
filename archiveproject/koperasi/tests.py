from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .forms import (
    BusinessTransactionForm,
    CashTransactionForm,
    LoanInstallmentForm,
    SavingTransactionForm,
)
from .models import (
    BusinessTransaction,
    CashTransaction,
    Company,
    KoperasiAccess,
    Loan,
    LoanInstallment,
    Member,
    PayrollDeduction,
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
    ARCHIVE_HOSTS=frozenset({"archive.localhost"}),
    LANDING_HOSTS=frozenset({"localhost"}),
    PORTAL_BASE_URL="https://pwujatim.site",
)


@HOST_SETTINGS
class KoperasiHostTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.get(username="it_pwu")
        self.user.role = "admin"
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.set_password("test-password")
        self.user.save()

    def test_koperasi_host_requires_login(self):
        response = self.client.get("/", HTTP_HOST="koperasi.localhost:8000")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_it_user_can_open_koperasi_dashboard(self):
        self.client.force_login(self.user)

        response = self.client.get("/", HTTP_HOST="koperasi.localhost:8000")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Koperasi Karyawan Wira Jatim")
        self.assertContains(response, "Sie Simpan Pinjam")
        self.assertContains(response, 'href="/report/"')
        self.assertContains(response, 'href="http://localhost:8000/settings/"')

    def test_it_user_can_open_koperasi_report_and_settings(self):
        self.client.force_login(self.user)

        report_response = self.client.get(
            "/report/",
            HTTP_HOST="koperasi.localhost:8000",
        )
        settings_response = self.client.get(
            "/pengaturan/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(report_response.status_code, 200)
        self.assertContains(report_response, "Report Bug")
        self.assertEqual(settings_response.status_code, 302)
        self.assertEqual(settings_response.url, "http://localhost:8000/settings/")

    def test_koperasi_login_redirects_to_central_portal(self):
        response = self.client.get(
            "/accounts/login/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("http://localhost:8000/accounts/login/"))

    def test_login_post_on_koperasi_is_redirected_to_central_portal(self):
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

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("http://localhost:8000/accounts/login/"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_archive_role_cannot_open_koperasi_settings(self):
        archive_user = get_user_model().objects.create_user(
            username="archive_settings_user",
            password="test-password",
            role="sekretaris",
        )
        self.client.force_login(archive_user)

        response = self.client.get(
            "/pengaturan/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "http://localhost:8000/settings/")

    def test_accountant_without_scope_assignment_can_open_dashboard(self):
        accountant = get_user_model().objects.create_user(
            username="akuntan_grup",
            password="test-password",
            role="akuntan",
        )
        KoperasiAccess.objects.create(
            user=accountant,
            company=None,
            role="auditor",
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

    def test_archive_user_with_koperasi_access_is_allowed(self):
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

        self.assertEqual(response.status_code, 200)

    def test_scoped_officer_cannot_manage_global_access(self):
        response = self.client.get(
            "/akses/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 403)

    def test_accountant_can_open_archive(self):
        response = self.client.get(
            "/",
            HTTP_HOST="archive.localhost:8000",
        )

        self.assertEqual(response.status_code, 200)

    def test_archive_login_is_also_centralized(self):
        self.client.logout()

        response = self.client.post(
            "/accounts/login/",
            {
                "username": self.user.username,
                "password": "test-password",
            },
            HTTP_HOST="archive.localhost:8000",
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("http://localhost:8000/accounts/login/"))
        self.assertNotIn("_auth_user_id", self.client.session)


@HOST_SETTINGS
class LoanWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="koperasi_manager",
            password="test-password",
            role="akuntan",
        )
        self.company, _created = Company.objects.get_or_create(
            code="PWU",
            defaults={"name": "PWU"},
        )
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


@HOST_SETTINGS
class CooperativeSpecificationWorkflowTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="WJ", name="Wira Jatim")
        self.member = Member.objects.create(
            member_number="WJ-001",
            company=self.company,
            full_name="Anggota Spesifikasi",
            join_date=date.today(),
            status="active",
        )
        self.chairman = get_user_model().objects.create_user(
            username="ketua_koperasi",
            password="test-password",
            role="akuntan",
        )
        self.savings_treasurer = get_user_model().objects.create_user(
            username="bendahara_simpan_pinjam",
            password="test-password",
            role="akuntan",
        )
        self.business_treasurer = get_user_model().objects.create_user(
            username="bendahara_usaha",
            password="test-password",
            role="akuntan",
        )
        KoperasiAccess.objects.create(
            user=self.chairman,
            company=None,
            role="chairman",
        )
        KoperasiAccess.objects.create(
            user=self.savings_treasurer,
            company=None,
            role="savings_treasurer",
        )
        KoperasiAccess.objects.create(
            user=self.business_treasurer,
            company=None,
            role="business_treasurer",
        )

    def test_member_application_can_be_approved(self):
        applicant = Member.objects.create(
            member_number="WJ-002",
            company=self.company,
            full_name="Calon Anggota",
            join_date=date.today(),
            status="pending",
        )
        self.client.force_login(self.chairman)

        response = self.client.post(
            f"/anggota/{applicant.pk}/status/approve/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 302)
        applicant.refresh_from_db()
        self.assertEqual(applicant.status, "active")
        self.assertEqual(applicant.approved_by, self.chairman)

    def test_savings_treasurer_has_same_management_controls_as_chairman(self):
        self.client.force_login(self.savings_treasurer)

        dashboard_response = self.client.get(
            "/",
            HTTP_HOST="koperasi.localhost:8000",
        )
        company_response = self.client.get(
            f"/perusahaan/{self.company.pk}/edit/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertTrue(dashboard_response.context["can_manage"])
        self.assertEqual(company_response.status_code, 200)

    def test_chairman_has_full_operational_write_access(self):
        self.client.force_login(self.chairman)

        writable_pages = [
            "/anggota/tambah/",
            "/simpanan/tambah/",
            "/pinjaman/tambah/",
            "/potongan-payroll/tambah/",
            "/sie-usaha/tambah/",
        ]
        responses = [
            self.client.get(path, HTTP_HOST="koperasi.localhost:8000")
            for path in writable_pages
        ]

        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertTrue(responses[0].context["can_write"])
        self.assertTrue(responses[0].context["can_approve_business"])
        automated_cash_response = self.client.get(
            "/kas/tambah/",
            HTTP_HOST="koperasi.localhost:8000",
        )
        self.assertRedirects(
            automated_cash_response,
            "/kas/",
            fetch_redirect_response=False,
        )

    def test_saving_transaction_form_does_not_show_reference(self):
        self.client.force_login(self.chairman)

        response = self.client.get(
            "/simpanan/tambah/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("reference", response.context["form"].fields)

    def test_transaction_forms_do_not_show_reference(self):
        forms = [
            SavingTransactionForm(),
            LoanInstallmentForm(),
            CashTransactionForm(),
            BusinessTransactionForm(),
        ]

        for form in forms:
            self.assertNotIn("reference", form.fields)

    def test_saving_transaction_can_be_viewed_and_edited(self):
        saving = SavingTransaction.objects.create(
            transaction_number="WJ-SAV-DETAIL",
            member=self.member,
            saving_type="mandatory",
            direction="deposit",
            transaction_date=date.today(),
            amount=Decimal("100000"),
            reference="Payroll 08/2026",
            notes="Catatan awal",
            created_by=self.savings_treasurer,
        )
        self.client.force_login(self.chairman)

        detail_response = self.client.get(
            f"/simpanan/{saving.pk}/",
            HTTP_HOST="koperasi.localhost:8000",
        )
        edit_page_response = self.client.get(
            f"/simpanan/{saving.pk}/edit/",
            HTTP_HOST="koperasi.localhost:8000",
        )
        list_response = self.client.get(
            "/simpanan/",
            HTTP_HOST="koperasi.localhost:8000",
        )
        edit_response = self.client.post(
            f"/simpanan/{saving.pk}/edit/",
            {
                "transaction_number": saving.transaction_number,
                "member": self.member.pk,
                "saving_type": "voluntary",
                "direction": "deposit",
                "transaction_date": date.today().isoformat(),
                "amount": "150000",
                "notes": "Catatan diperbarui",
            },
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "WJ-SAV-DETAIL")
        self.assertContains(detail_response, "Edit Transaksi")
        self.assertContains(edit_page_response, f'href="/simpanan/{saving.pk}/"')
        self.assertNotContains(edit_page_response, "history.back()")
        self.assertContains(list_response, ">Detail</a>")
        self.assertNotContains(list_response, ">Edit</a>")
        self.assertRedirects(
            edit_response,
            f"/simpanan/{saving.pk}/",
            fetch_redirect_response=False,
        )
        saving.refresh_from_db()
        self.assertEqual(saving.saving_type, "voluntary")
        self.assertEqual(saving.amount, Decimal("150000"))
        self.assertEqual(saving.reference, "Payroll 08/2026")

    def test_saving_transaction_can_be_deleted_from_edit_flow(self):
        saving = SavingTransaction.objects.create(
            transaction_number="WJ-SAV-DELETE",
            member=self.member,
            saving_type="mandatory",
            direction="deposit",
            transaction_date=date.today(),
            amount=Decimal("100000"),
            created_by=self.savings_treasurer,
        )
        self.client.force_login(self.chairman)

        edit_response = self.client.get(
            f"/simpanan/{saving.pk}/edit/",
            HTTP_HOST="koperasi.localhost:8000",
        )
        confirmation_response = self.client.get(
            f"/simpanan/{saving.pk}/hapus/",
            HTTP_HOST="koperasi.localhost:8000",
        )
        delete_response = self.client.post(
            f"/simpanan/{saving.pk}/hapus/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertContains(edit_response, "Hapus Transaksi")
        self.assertContains(confirmation_response, "Ya, Hapus Transaksi")
        self.assertRedirects(
            delete_response,
            "/simpanan/",
            fetch_redirect_response=False,
        )
        self.assertFalse(SavingTransaction.objects.filter(pk=saving.pk).exists())

    def test_saving_list_can_filter_deposits_and_withdrawals(self):
        SavingTransaction.objects.create(
            transaction_number="WJ-SAV-DEPOSIT-FILTER",
            member=self.member,
            saving_type="mandatory",
            direction="deposit",
            transaction_date=date.today(),
            amount=Decimal("100000"),
            created_by=self.savings_treasurer,
        )
        SavingTransaction.objects.create(
            transaction_number="WJ-SAV-WITHDRAW-FILTER",
            member=self.member,
            saving_type="voluntary",
            direction="withdrawal",
            transaction_date=date.today(),
            amount=Decimal("50000"),
            created_by=self.savings_treasurer,
        )
        self.client.force_login(self.chairman)

        deposit_response = self.client.get(
            "/simpanan/?direction=deposit",
            HTTP_HOST="koperasi.localhost:8000",
        )
        withdrawal_response = self.client.get(
            "/simpanan/?direction=withdrawal",
            HTTP_HOST="koperasi.localhost:8000",
        )
        all_response = self.client.get(
            "/simpanan/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertContains(deposit_response, "WJ-SAV-DEPOSIT-FILTER")
        self.assertNotContains(deposit_response, "WJ-SAV-WITHDRAW-FILTER")
        self.assertContains(withdrawal_response, "WJ-SAV-WITHDRAW-FILTER")
        self.assertNotContains(withdrawal_response, "WJ-SAV-DEPOSIT-FILTER")
        self.assertContains(all_response, "WJ-SAV-DEPOSIT-FILTER")
        self.assertContains(all_response, "WJ-SAV-WITHDRAW-FILTER")

    def test_saving_list_can_filter_saving_type(self):
        transactions = [
            ("WJ-SAV-PRINCIPAL-FILTER", "principal"),
            ("WJ-SAV-MANDATORY-FILTER", "mandatory"),
            ("WJ-SAV-VOLUNTARY-FILTER", "voluntary"),
        ]
        for transaction_number, saving_type in transactions:
            SavingTransaction.objects.create(
                transaction_number=transaction_number,
                member=self.member,
                saving_type=saving_type,
                direction="deposit",
                transaction_date=date.today(),
                amount=Decimal("100000"),
                created_by=self.savings_treasurer,
            )
        self.client.force_login(self.chairman)

        response = self.client.get(
            "/simpanan/?saving_type=mandatory",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertContains(response, "WJ-SAV-MANDATORY-FILTER")
        self.assertNotContains(response, "WJ-SAV-PRINCIPAL-FILTER")
        self.assertNotContains(response, "WJ-SAV-VOLUNTARY-FILTER")

    def test_saving_has_transaction_list_and_annual_recap_views(self):
        SavingTransaction.objects.create(
            transaction_number="WJ-SAV-RECAP-POKOK",
            member=self.member,
            saving_type="principal",
            direction="deposit",
            transaction_date=date(2026, 1, 10),
            amount=Decimal("100000"),
            created_by=self.savings_treasurer,
        )
        SavingTransaction.objects.create(
            transaction_number="WJ-SAV-RECAP-WAJIB",
            member=self.member,
            saving_type="mandatory",
            direction="deposit",
            transaction_date=date(2026, 2, 10),
            amount=Decimal("300000"),
            created_by=self.savings_treasurer,
        )
        SavingTransaction.objects.create(
            transaction_number="WJ-SAV-RECAP-OLD",
            member=self.member,
            saving_type="voluntary",
            direction="deposit",
            transaction_date=date(2025, 12, 10),
            amount=Decimal("999999"),
            created_by=self.savings_treasurer,
        )
        self.client.force_login(self.chairman)

        list_response = self.client.get(
            "/simpanan/?view=list",
            HTTP_HOST="koperasi.localhost:8000",
        )
        table_response = self.client.get(
            f"/simpanan/?view=table&year=2026&company={self.company.pk}",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertContains(list_response, "Daftar Transaksi")
        self.assertContains(list_response, "WJ-SAV-RECAP-POKOK")
        self.assertContains(table_response, "REKAPITULASI SIMPANAN")
        self.assertContains(table_response, self.member.full_name)
        self.assertContains(table_response, "Rp 400.000")
        self.assertNotContains(table_response, "Rp 999.999")
        self.assertEqual(table_response.context["selected_view"], "table")

    def test_chairman_can_approve_business_transaction(self):
        business_row = BusinessTransaction.objects.create(
            transaction_number="WJ-BIZ-CHAIRMAN",
            company=self.company,
            member=self.member,
            transaction_date=date.today(),
            activity_type="rice_purchase",
            direction="expense",
            description="Pembelian beras anggota",
            quantity=Decimal("1"),
            unit_price=Decimal("100000"),
            payment_method="cash",
            status="submitted",
            created_by=self.business_treasurer,
        )
        self.client.force_login(self.chairman)

        response = self.client.post(
            f"/sie-usaha/{business_row.pk}/status/approve/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 302)
        business_row.refresh_from_db()
        self.assertEqual(business_row.status, "approved")
        self.assertEqual(business_row.approved_by, self.chairman)

    def test_business_list_filters_activity_payment_and_status(self):
        matching = BusinessTransaction.objects.create(
            transaction_number="WJ-BIZ-FILTER-MATCH",
            company=self.company,
            member=self.member,
            transaction_date=date.today(),
            activity_type="rice_purchase",
            direction="expense",
            description="Transaksi sesuai filter",
            quantity=Decimal("1"),
            unit_price=Decimal("100000"),
            payment_method="payroll",
            status="submitted",
            created_by=self.business_treasurer,
        )
        BusinessTransaction.objects.create(
            transaction_number="WJ-BIZ-FILTER-OTHER",
            company=self.company,
            member=self.member,
            transaction_date=date.today(),
            activity_type="office_procurement",
            direction="expense",
            description="Transaksi berbeda",
            quantity=Decimal("1"),
            unit_price=Decimal("200000"),
            payment_method="cash",
            status="approved",
            created_by=self.business_treasurer,
        )
        self.client.force_login(self.chairman)

        response = self.client.get(
            "/sie-usaha/?activity=rice_purchase&payment=payroll&status=submitted",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertContains(response, matching.transaction_number)
        self.assertNotContains(response, "WJ-BIZ-FILTER-OTHER")
        self.assertEqual(response.context["selected_activity"], "rice_purchase")
        self.assertEqual(response.context["selected_payment"], "payroll")
        self.assertEqual(response.context["selected_status"], "submitted")

    def test_cash_bank_ledger_is_automatic_and_filters_period_and_unit(self):
        SavingTransaction.objects.create(
            transaction_number="WJ-LEDGER-SAVING",
            member=self.member,
            saving_type="mandatory",
            direction="deposit",
            transaction_date=date(2026, 2, 10),
            amount=Decimal("150000"),
            created_by=self.savings_treasurer,
        )
        BusinessTransaction.objects.create(
            transaction_number="WJ-LEDGER-BUSINESS",
            company=self.company,
            member=self.member,
            transaction_date=date(2026, 2, 11),
            activity_type="office_procurement",
            direction="expense",
            description="Pengadaan perlengkapan",
            quantity=Decimal("1"),
            unit_price=Decimal("50000"),
            payment_method="transfer",
            status="approved",
            created_by=self.business_treasurer,
        )
        self.client.force_login(self.chairman)

        all_response = self.client.get(
            "/kas/?year=2026&month=2",
            HTTP_HOST="koperasi.localhost:8000",
        )
        savings_response = self.client.get(
            "/kas/?year=2026&month=2&unit=savings_loan",
            HTTP_HOST="koperasi.localhost:8000",
        )
        manual_response = self.client.get(
            "/kas/tambah/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertContains(all_response, "WJ-LEDGER-SAVING")
        self.assertContains(all_response, "WJ-LEDGER-BUSINESS")
        self.assertEqual(all_response.context["closing_cash"], Decimal("150000"))
        self.assertEqual(all_response.context["closing_bank"], Decimal("-50000"))
        self.assertContains(savings_response, "WJ-LEDGER-SAVING")
        self.assertNotContains(savings_response, "WJ-LEDGER-BUSINESS")
        self.assertRedirects(
            manual_response,
            "/kas/",
            fetch_redirect_response=False,
        )

    def test_add_member_form_does_not_show_system_user(self):
        self.client.force_login(self.savings_treasurer)

        response = self.client.get(
            "/anggota/tambah/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("user", response.context["form"].fields)

    def test_member_list_has_real_detail_link(self):
        self.client.force_login(self.savings_treasurer)

        response = self.client.get(
            "/anggota/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="/anggota/{self.member.pk}/"')
        self.assertContains(response, ">Detail</a>")

    def test_member_can_be_deleted_from_edit_flow_when_without_history(self):
        removable_member = Member.objects.create(
            member_number="WJ-DELETE",
            company=self.company,
            full_name="Anggota Dihapus",
            join_date=date.today(),
            status="pending",
        )
        self.client.force_login(self.savings_treasurer)

        edit_response = self.client.get(
            f"/anggota/{removable_member.pk}/edit/",
            HTTP_HOST="koperasi.localhost:8000",
        )
        delete_response = self.client.post(
            f"/anggota/{removable_member.pk}/hapus/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertContains(edit_response, "Hapus Anggota")
        self.assertRedirects(
            delete_response,
            "/anggota/",
            fetch_redirect_response=False,
        )
        self.assertFalse(Member.objects.filter(pk=removable_member.pk).exists())

    def test_member_with_financial_history_cannot_be_deleted(self):
        SavingTransaction.objects.create(
            transaction_number="WJ-SAV-PROTECTED",
            member=self.member,
            saving_type="mandatory",
            direction="deposit",
            transaction_date=date.today(),
            amount=Decimal("100000"),
            created_by=self.savings_treasurer,
        )
        self.client.force_login(self.savings_treasurer)

        response = self.client.post(
            f"/anggota/{self.member.pk}/hapus/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertRedirects(
            response,
            f"/anggota/{self.member.pk}/edit/",
            fetch_redirect_response=False,
        )
        self.assertTrue(Member.objects.filter(pk=self.member.pk).exists())

    def test_loan_requires_chairman_and_savings_treasurer_approval(self):
        loan = Loan.objects.create(
            loan_number="WJ-PIN-001",
            member=self.member,
            application_date=date.today(),
            principal_amount=Decimal("1000000"),
            interest_rate=Decimal("12"),
            term_months=12,
            purpose="Kebutuhan anggota",
            status="submitted",
            created_by=self.savings_treasurer,
        )
        self.client.force_login(self.chairman)
        self.client.post(
            f"/pinjaman/{loan.pk}/status/approve/",
            HTTP_HOST="koperasi.localhost:8000",
        )
        loan.refresh_from_db()
        self.assertEqual(loan.status, "submitted")
        self.assertIsNotNone(loan.chairman_approved_at)
        self.assertIsNone(loan.savings_treasurer_approved_at)

        self.client.force_login(self.savings_treasurer)
        response = self.client.post(
            f"/pinjaman/{loan.pk}/status/approve/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.status, "approved")
        self.assertIsNotNone(loan.savings_treasurer_approved_at)

    def test_posting_payroll_creates_savings_and_installment(self):
        loan = Loan.objects.create(
            loan_number="WJ-PIN-002",
            member=self.member,
            application_date=date.today(),
            principal_amount=Decimal("1200000"),
            interest_rate=Decimal("0"),
            term_months=12,
            purpose="Uji payroll",
            status="active",
            created_by=self.savings_treasurer,
        )
        deduction = PayrollDeduction.objects.create(
            member=self.member,
            period=date.today().replace(day=1),
            mandatory_saving=Decimal("25000"),
            voluntary_saving=Decimal("10000"),
            loan_principal=Decimal("100000"),
            created_by=self.savings_treasurer,
        )
        self.client.force_login(self.savings_treasurer)

        response = self.client.post(
            f"/potongan-payroll/{deduction.pk}/bukukan/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 302)
        deduction.refresh_from_db()
        self.assertEqual(deduction.status, "posted")
        self.assertEqual(
            SavingTransaction.objects.filter(member=self.member).count(),
            2,
        )
        self.assertEqual(loan.installments.count(), 1)

    def test_payroll_recap_is_separated_by_company_and_period(self):
        other_company = Company.objects.create(code="WJ2", name="Wira Jatim Dua")
        other_member = Member.objects.create(
            member_number="WJ2-001",
            company=other_company,
            full_name="Anggota Perusahaan Dua",
            join_date=date.today(),
            status="active",
        )
        PayrollDeduction.objects.create(
            member=self.member,
            period=date(2026, 1, 1),
            mandatory_saving=Decimal("25000"),
            voluntary_saving=Decimal("10000"),
            loan_principal=Decimal("100000"),
            created_by=self.savings_treasurer,
        )
        PayrollDeduction.objects.create(
            member=other_member,
            period=date(2026, 1, 1),
            mandatory_saving=Decimal("30000"),
            created_by=self.savings_treasurer,
        )
        PayrollDeduction.objects.create(
            member=self.member,
            period=date(2026, 2, 1),
            mandatory_saving=Decimal("99999"),
            created_by=self.savings_treasurer,
        )
        self.client.force_login(self.chairman)

        response = self.client.get(
            "/potongan-payroll/?year=2026&month=1",
            HTTP_HOST="koperasi.localhost:8000",
        )
        company_response = self.client.get(
            f"/potongan-payroll/?year=2026&month=1&company={self.company.pk}",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.context["company_books"]), 2)
        self.assertContains(response, self.company.name)
        self.assertContains(response, other_company.name)
        self.assertContains(response, "Rp 135.000")
        self.assertNotContains(response, "Rp 99.999")
        self.assertEqual(len(company_response.context["company_books"]), 1)
        self.assertContains(company_response, self.member.full_name)
        self.assertNotContains(company_response, other_member.full_name)

    def test_business_treasurer_can_approve_business_transaction(self):
        business_row = BusinessTransaction.objects.create(
            transaction_number="USAHA-001",
            company=self.company,
            member=self.member,
            transaction_date=date.today(),
            activity_type="rice_purchase",
            direction="expense",
            description="Pembelian beras anggota",
            quantity=Decimal("10"),
            unit="kg",
            unit_price=Decimal("15000"),
            created_by=self.business_treasurer,
        )
        self.client.force_login(self.business_treasurer)

        response = self.client.post(
            f"/sie-usaha/{business_row.pk}/status/approve/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 302)
        business_row.refresh_from_db()
        self.assertEqual(business_row.status, "approved")
        self.assertEqual(business_row.total_amount, Decimal("150000.00"))

    def test_financial_report_contains_specification_sections(self):
        self.client.force_login(self.chairman)

        response = self.client.get(
            "/laporan/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Neraca")
        self.assertContains(response, "Laporan Hasil Usaha")
        self.assertContains(response, "Laporan Arus Kas")
        self.assertContains(response, "Pembagian Sisa Hasil Usaha")

    def test_loan_book_shows_disbursement_installment_and_running_balance(self):
        loan = Loan.objects.create(
            loan_number="WJ-BOOK-001",
            member=self.member,
            application_date=date(2026, 8, 1),
            disbursed_date=date(2026, 8, 2),
            principal_amount=Decimal("1200000"),
            interest_rate=Decimal("0"),
            term_months=12,
            purpose="Uji buku pinjaman",
            status="active",
            created_by=self.savings_treasurer,
        )
        LoanInstallment.objects.create(
            loan=loan,
            payment_number="WJ-PAY-BOOK-001",
            payment_date=date(2026, 9, 2),
            principal_amount=Decimal("100000"),
            interest_amount=Decimal("0"),
            penalty_amount=Decimal("0"),
            received_by=self.savings_treasurer,
        )
        self.client.force_login(self.savings_treasurer)

        response = self.client.get(
            f"/pinjaman/{loan.pk}/buku/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Buku Pinjaman Anggota")
        self.assertContains(response, "WJ-PAY-BOOK-001")
        self.assertContains(response, "Rp 1.100.000")

    def test_automatic_cash_row_can_generate_printable_voucher(self):
        saving = SavingTransaction.objects.create(
            transaction_number="WJ-VCR-001",
            member=self.member,
            saving_type="mandatory",
            direction="deposit",
            transaction_date=date.today(),
            amount=Decimal("25000"),
            created_by=self.savings_treasurer,
        )
        self.client.force_login(self.savings_treasurer)

        list_response = self.client.get(
            "/kas/",
            HTTP_HOST="koperasi.localhost:8000",
        )
        voucher_response = self.client.get(
            f"/kas/bukti/saving/{saving.pk}/",
            HTTP_HOST="koperasi.localhost:8000",
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, f"/kas/bukti/saving/{saving.pk}/")
        self.assertEqual(voucher_response.status_code, 200)
        self.assertContains(voucher_response, "Kas Masuk")
        self.assertContains(voucher_response, "dua puluh lima ribu rupiah")
