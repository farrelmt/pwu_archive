from django.contrib import admin

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


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "company_type", "is_active")
    search_fields = ("code", "name")
    list_filter = ("company_type", "is_active")


@admin.register(KoperasiAccess)
class KoperasiAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "company", "is_active")
    list_filter = ("role", "is_active", "company")


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("member_number", "full_name", "company", "status", "join_date")
    search_fields = ("member_number", "full_name", "employee_number")
    list_filter = ("company", "status")


@admin.register(SavingTransaction)
class SavingTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_number",
        "member",
        "saving_type",
        "direction",
        "amount",
        "transaction_date",
    )
    list_filter = ("saving_type", "direction", "transaction_date")


class LoanInstallmentInline(admin.TabularInline):
    model = LoanInstallment
    extra = 0


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = (
        "loan_number",
        "member",
        "principal_amount",
        "term_months",
        "status",
    )
    list_filter = ("status", "member__company")
    inlines = [LoanInstallmentInline]


@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_number",
        "company",
        "transaction_type",
        "unit",
        "account",
        "category",
        "amount",
        "transaction_date",
    )
    list_filter = ("company", "unit", "account", "transaction_type", "transaction_date")


@admin.register(PayrollDeduction)
class PayrollDeductionAdmin(admin.ModelAdmin):
    list_display = ("period", "member", "total_amount", "status")
    list_filter = ("period", "status", "member__company")
    search_fields = ("member__member_number", "member__full_name")


@admin.register(BusinessTransaction)
class BusinessTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_number",
        "transaction_date",
        "activity_type",
        "direction",
        "total_amount",
        "status",
    )
    list_filter = ("activity_type", "direction", "status", "company")
    search_fields = ("transaction_number", "description", "member__full_name")
