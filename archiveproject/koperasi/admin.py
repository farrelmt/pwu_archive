from django.contrib import admin

from .models import (
    CashTransaction,
    Company,
    KoperasiAccess,
    Loan,
    LoanInstallment,
    Member,
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
        "category",
        "amount",
        "transaction_date",
    )
    list_filter = ("company", "transaction_type", "transaction_date")

