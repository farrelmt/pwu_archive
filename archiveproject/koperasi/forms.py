from django import forms
from django.core.exceptions import ValidationError

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


INPUT_CLASS = (
    "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm "
    "text-slate-800 outline-none transition focus:border-blue-500 "
    "focus:ring-4 focus:ring-blue-100"
)
CHECKBOX_CLASS = "h-4 w-4 rounded border-slate-300 text-blue-700 focus:ring-blue-500"


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = CHECKBOX_CLASS
            else:
                field.widget.attrs["class"] = INPUT_CLASS
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("rows", 3)


class CompanyForm(StyledModelForm):
    class Meta:
        model = Company
        fields = [
            "code",
            "name",
            "company_type",
            "registration_number",
            "email",
            "phone",
            "address",
            "is_active",
        ]


class KoperasiAccessForm(StyledModelForm):
    class Meta:
        model = KoperasiAccess
        fields = ["user", "company", "role", "is_active"]


class MemberForm(StyledModelForm):
    class Meta:
        model = Member
        fields = [
            "member_number",
            "company",
            "user",
            "employee_number",
            "full_name",
            "email",
            "phone",
            "address",
            "join_date",
            "status",
            "mandatory_saving_amount",
        ]
        widgets = {
            "join_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, companies=None, include_user=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not include_user:
            self.fields.pop("user", None)
        if companies is not None:
            self.fields["company"].queryset = companies


class SavingTransactionForm(StyledModelForm):
    class Meta:
        model = SavingTransaction
        fields = [
            "transaction_number",
            "member",
            "saving_type",
            "direction",
            "transaction_date",
            "amount",
            "notes",
        ]
        widgets = {
            "transaction_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, members=None, **kwargs):
        super().__init__(*args, **kwargs)
        if members is not None:
            self.fields["member"].queryset = members

    def clean(self):
        cleaned = super().clean()
        member = cleaned.get("member")
        direction = cleaned.get("direction")
        saving_type = cleaned.get("saving_type")
        amount = cleaned.get("amount")
        if (
            member
            and direction == "withdrawal"
            and amount
            and amount > member.saving_balance(saving_type)
        ):
            raise ValidationError(
                "Penarikan melebihi saldo pada jenis simpanan yang dipilih."
            )
        return cleaned


class LoanForm(StyledModelForm):
    class Meta:
        model = Loan
        fields = [
            "loan_number",
            "member",
            "application_date",
            "principal_amount",
            "interest_rate",
            "term_months",
            "payment_method",
            "payment_due_day",
            "purpose",
            "notes",
        ]
        widgets = {
            "application_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, members=None, **kwargs):
        super().__init__(*args, **kwargs)
        if members is not None:
            self.fields["member"].queryset = members.filter(status="active")


class LoanInstallmentForm(StyledModelForm):
    class Meta:
        model = LoanInstallment
        fields = [
            "payment_number",
            "payment_date",
            "principal_amount",
            "interest_amount",
            "penalty_amount",
            "notes",
        ]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, loan=None, **kwargs):
        self.loan = loan
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        principal = cleaned.get("principal_amount") or 0
        interest = cleaned.get("interest_amount") or 0
        if self.loan and principal + interest > self.loan.outstanding_amount:
            raise ValidationError(
                "Pembayaran pokok dan bunga melebihi sisa pinjaman."
            )
        if principal + interest <= 0:
            raise ValidationError(
                "Pembayaran harus memiliki nilai pokok atau bunga."
            )
        return cleaned


class CashTransactionForm(StyledModelForm):
    class Meta:
        model = CashTransaction
        fields = [
            "transaction_number",
            "company",
            "transaction_date",
            "transaction_type",
            "unit",
            "account",
            "category",
            "amount",
            "counterparty",
            "description",
        ]
        widgets = {
            "transaction_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, companies=None, **kwargs):
        super().__init__(*args, **kwargs)
        if companies is not None:
            self.fields["company"].queryset = companies


class PayrollDeductionForm(StyledModelForm):
    class Meta:
        model = PayrollDeduction
        fields = [
            "member",
            "period",
            "principal_saving",
            "mandatory_saving",
            "voluntary_saving",
            "loan_principal",
            "loan_interest",
            "business_deduction",
            "notes",
        ]
        widgets = {
            "period": forms.DateInput(attrs={"type": "month"}),
        }

    def __init__(self, *args, members=None, **kwargs):
        super().__init__(*args, **kwargs)
        if members is not None:
            self.fields["member"].queryset = members.filter(status="active")

    def clean_period(self):
        period = self.cleaned_data["period"]
        return period.replace(day=1)

    def clean(self):
        cleaned = super().clean()
        amount_fields = (
            "principal_saving",
            "mandatory_saving",
            "voluntary_saving",
            "loan_principal",
            "loan_interest",
            "business_deduction",
        )
        if any((cleaned.get(field) or 0) < 0 for field in amount_fields):
            raise ValidationError("Nilai potongan tidak boleh negatif.")
        if not any((cleaned.get(field) or 0) > 0 for field in amount_fields):
            raise ValidationError("Isi setidaknya satu nilai potongan.")
        return cleaned


class BusinessTransactionForm(StyledModelForm):
    class Meta:
        model = BusinessTransaction
        fields = [
            "transaction_number",
            "company",
            "member",
            "transaction_date",
            "activity_type",
            "direction",
            "description",
            "quantity",
            "unit",
            "unit_price",
            "payment_method",
            "notes",
        ]
        widgets = {
            "transaction_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, companies=None, members=None, **kwargs):
        super().__init__(*args, **kwargs)
        if companies is not None:
            self.fields["company"].queryset = companies
        if members is not None:
            self.fields["member"].queryset = members.filter(status="active")

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get("company")
        member = cleaned.get("member")
        if member and company and member.company_id != company.pk:
            raise ValidationError(
                "Perusahaan anggota harus sama dengan perusahaan transaksi."
            )
        return cleaned
