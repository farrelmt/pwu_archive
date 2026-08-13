import textwrap
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from accounts.audit import record_activity
from homepage.forms import ReportForm

from .access import (
    APPROVE_ROLES,
    can_manage_global_access,
    koperasi_admin_required,
    koperasi_manage_required,
    koperasi_required,
    koperasi_write_required,
)
from .forms import (
    BusinessTransactionForm,
    CashTransactionForm,
    CompanyForm,
    KoperasiAccessForm,
    LoanForm,
    LoanInstallmentForm,
    MemberForm,
    PayrollDeductionForm,
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


def _log(request, action, description, target):
    record_activity(
        category="KOPERASI",
        action=action,
        description=description,
        request=request,
        target_type=target.__class__.__name__,
        target_id=target.pk,
        target_label=str(target),
    )


def _base_context(request):
    roles = getattr(request, "koperasi_roles", set())
    is_admin = request.user.is_superuser or bool(roles.intersection({"admin", "manager"}))
    return {
        "koperasi_roles": roles,
        "can_write": bool(
            roles.intersection(
                {
                    "admin",
                    "manager",
                    "chairman",
                    "finance",
                    "officer",
                    "treasurer",
                    "savings_treasurer",
                    "business_treasurer",
                    "member_section",
                }
            )
        ),
        "can_manage": bool(
            roles.intersection(
                {
                    "admin",
                    "manager",
                    "chairman",
                    "treasurer",
                    "savings_treasurer",
                }
            )
        ),
        "can_approve": bool(roles.intersection(APPROVE_ROLES)),
        "can_approve_member": is_admin
        or bool(roles.intersection({"chairman", "savings_treasurer"})),
        "can_approve_loan": is_admin
        or bool(roles.intersection({"chairman", "savings_treasurer"})),
        "can_approve_business": is_admin
        or bool(roles.intersection({"chairman", "business_treasurer"})),
        "can_admin_access": can_manage_global_access(request.user),
    }


def _scoped_members(request):
    return Member.objects.select_related("company").filter(
        company__in=request.koperasi_companies
    )


def _scoped_loans(request):
    return Loan.objects.select_related("member", "member__company").filter(
        member__company__in=request.koperasi_companies
    )


def _selected_company(request):
    company_id = request.GET.get("company", "").strip()
    if company_id.isdigit():
        return request.koperasi_companies.filter(pk=company_id).first()
    return None


def _ledger_account(payment_method="", reference=""):
    if reference.lower().startswith("payroll"):
        return "bank"
    if payment_method in {"transfer", "payroll", "meal_allowance"}:
        return "bank"
    return "cash"


def _terbilang(value):
    words = [
        "nol", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh",
        "delapan", "sembilan", "sepuluh", "sebelas",
    ]

    def spell(number):
        number = int(number)
        if number < 12:
            return words[number]
        if number < 20:
            return f"{spell(number - 10)} belas"
        if number < 100:
            return f"{spell(number // 10)} puluh" + (
                f" {spell(number % 10)}" if number % 10 else ""
            )
        if number < 200:
            return "seratus" + (f" {spell(number - 100)}" if number > 100 else "")
        if number < 1000:
            return f"{spell(number // 100)} ratus" + (
                f" {spell(number % 100)}" if number % 100 else ""
            )
        if number < 2000:
            return "seribu" + (f" {spell(number - 1000)}" if number > 1000 else "")
        if number < 1_000_000:
            return f"{spell(number // 1000)} ribu" + (
                f" {spell(number % 1000)}" if number % 1000 else ""
            )
        if number < 1_000_000_000:
            return f"{spell(number // 1_000_000)} juta" + (
                f" {spell(number % 1_000_000)}" if number % 1_000_000 else ""
            )
        if number < 1_000_000_000_000:
            return f"{spell(number // 1_000_000_000)} miliar" + (
                f" {spell(number % 1_000_000_000)}"
                if number % 1_000_000_000
                else ""
            )
        return f"{spell(number // 1_000_000_000_000)} triliun" + (
            f" {spell(number % 1_000_000_000_000)}"
            if number % 1_000_000_000_000
            else ""
        )

    return f"{spell(Decimal(value or 0).quantize(Decimal('1')))} rupiah"


def _cash_bank_ledger(companies, selected_unit=""):
    company_ids = list(companies.values_list("pk", flat=True))
    rows = []

    def add_row(
        *, row_date, number, unit, description, account, direction, amount,
        source, source_type, source_pk,
    ):
        if selected_unit and unit != selected_unit:
            return
        amount = Decimal(amount or 0)
        rows.append(
            {
                "date": row_date,
                "number": number,
                "unit": unit,
                "description": description,
                "cash_debit": amount if account == "cash" and direction == "income" else Decimal("0"),
                "cash_credit": amount if account == "cash" and direction == "expense" else Decimal("0"),
                "bank_debit": amount if account == "bank" and direction == "income" else Decimal("0"),
                "bank_credit": amount if account == "bank" and direction == "expense" else Decimal("0"),
                "source": source,
                "source_type": source_type,
                "source_pk": source_pk,
            }
        )

    savings = SavingTransaction.objects.select_related("member").filter(
        member__company_id__in=company_ids
    )
    for saving in savings:
        add_row(
            row_date=saving.transaction_date,
            number=saving.transaction_number,
            unit="savings_loan",
            description=f"{saving.get_direction_display()} {saving.get_saving_type_display()} - {saving.member.full_name}",
            account=_ledger_account(reference=saving.reference),
            direction="income" if saving.direction == "deposit" else "expense",
            amount=saving.amount,
            source="Simpanan",
            source_type="saving",
            source_pk=saving.pk,
        )

    loans = Loan.objects.select_related("member").filter(
        member__company_id__in=company_ids,
        disbursed_date__isnull=False,
        status__in={"active", "paid"},
    )
    for loan in loans:
        add_row(
            row_date=loan.disbursed_date,
            number=loan.loan_number,
            unit="savings_loan",
            description=f"Pencairan pinjaman - {loan.member.full_name}",
            account=_ledger_account(loan.payment_method),
            direction="expense",
            amount=loan.principal_amount,
            source="Pinjaman",
            source_type="loan",
            source_pk=loan.pk,
        )

    installments = LoanInstallment.objects.select_related("loan", "loan__member").filter(
        loan__member__company_id__in=company_ids
    )
    for installment in installments:
        add_row(
            row_date=installment.payment_date,
            number=installment.payment_number,
            unit="savings_loan",
            description=f"Angsuran pinjaman - {installment.loan.member.full_name}",
            account=_ledger_account(
                installment.loan.payment_method,
                installment.reference,
            ),
            direction="income",
            amount=installment.total_amount,
            source="Angsuran",
            source_type="installment",
            source_pk=installment.pk,
        )

    business_rows = BusinessTransaction.objects.select_related("member").filter(
        company_id__in=company_ids,
        status__in={"approved", "completed"},
    )
    for business in business_rows:
        member_label = f" - {business.member.full_name}" if business.member else ""
        add_row(
            row_date=business.transaction_date,
            number=business.transaction_number,
            unit="business",
            description=f"{business.get_activity_type_display()}{member_label}: {business.description}",
            account=_ledger_account(business.payment_method),
            direction=business.direction,
            amount=business.total_amount,
            source="Sie Usaha",
            source_type="business",
            source_pk=business.pk,
        )

    legacy_rows = CashTransaction.objects.filter(company_id__in=company_ids)
    for cash_row in legacy_rows:
        add_row(
            row_date=cash_row.transaction_date,
            number=cash_row.transaction_number,
            unit=cash_row.unit,
            description=f"{cash_row.category}: {cash_row.description}",
            account=cash_row.account,
            direction=cash_row.transaction_type,
            amount=cash_row.amount,
            source="Data kas lama",
            source_type="cash",
            source_pk=cash_row.pk,
        )

    return sorted(rows, key=lambda row: (row["date"], row["number"]))


@koperasi_required
def dashboard(request):
    companies = request.koperasi_companies.filter(is_active=True)
    members = _scoped_members(request)
    loans = _scoped_loans(request)
    savings = SavingTransaction.objects.filter(member__in=members)
    business = BusinessTransaction.objects.filter(company__in=companies)

    deposits = savings.filter(direction="deposit").aggregate(
        value=Coalesce(Sum("amount"), Decimal("0"))
    )["value"]
    withdrawals = savings.filter(direction="withdrawal").aggregate(
        value=Coalesce(Sum("amount"), Decimal("0"))
    )["value"]
    ledger_rows = _cash_bank_ledger(companies)
    ledger_balance = sum(
        (
            row["cash_debit"]
            + row["bank_debit"]
            - row["cash_credit"]
            - row["bank_credit"]
            for row in ledger_rows
        ),
        Decimal("0"),
    )

    context = _base_context(request)
    context.update(
        {
            "company_count": companies.count(),
            "member_count": members.filter(status="active").count(),
            "saving_balance": deposits - withdrawals,
            "active_loan_count": loans.filter(
                status__in=["submitted", "approved", "active"]
            ).count(),
            "active_loan_value": loans.filter(status="active").aggregate(
                value=Coalesce(Sum("principal_amount"), Decimal("0"))
            )["value"],
            "cash_balance": ledger_balance,
            "pending_member_count": members.filter(status="pending").count(),
            "pending_loan_count": loans.filter(status="submitted").count(),
            "pending_business_count": business.filter(status="submitted").count(),
            "recent_savings": savings.select_related(
                "member", "member__company"
            )[:6],
            "recent_loans": loans[:6],
            "company_summaries": [
                {
                    "company": company,
                    "members": members.filter(
                        company=company, status="active"
                    ).count(),
                    "loans": loans.filter(
                        member__company=company, status="active"
                    ).count(),
                }
                for company in companies
            ],
        }
    )
    return render(request, "koperasi/dashboard.html", context)


@koperasi_required
def company_list(request):
    context = _base_context(request)
    context["companies"] = request.koperasi_companies.annotate(
        member_count=Count("members", distinct=True)
    )
    return render(request, "koperasi/company_list.html", context)


@koperasi_admin_required
def company_create(request):
    form = CompanyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        company = form.save()
        _log(request, "COMPANY_CREATED", "Menambahkan perusahaan.", company)
        messages.success(request, "Perusahaan berhasil ditambahkan.")
        return redirect("koperasi:companies")
    context = _base_context(request)
    context.update({"form": form, "form_title": "Tambah Perusahaan"})
    return render(request, "koperasi/form.html", context)


@koperasi_manage_required
def company_edit(request, pk):
    company = get_object_or_404(request.koperasi_companies, pk=pk)
    form = CompanyForm(request.POST or None, instance=company)
    if request.method == "POST" and form.is_valid():
        company = form.save()
        _log(request, "COMPANY_UPDATED", "Memperbarui perusahaan.", company)
        messages.success(request, "Perusahaan berhasil diperbarui.")
        return redirect("koperasi:companies")
    context = _base_context(request)
    context.update({"form": form, "form_title": "Edit Perusahaan"})
    return render(request, "koperasi/form.html", context)


@koperasi_required
def member_list(request):
    members = _scoped_members(request)
    selected_company = _selected_company(request)
    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if selected_company:
        members = members.filter(company=selected_company)
    if search:
        members = members.filter(
            Q(member_number__icontains=search)
            | Q(full_name__icontains=search)
            | Q(employee_number__icontains=search)
        )
    if status in dict(Member.STATUS_CHOICES):
        members = members.filter(status=status)
    context = _base_context(request)
    context.update(
        {
            "members": members,
            "companies": request.koperasi_companies,
            "selected_company": selected_company,
            "search": search,
            "selected_status": status,
            "statuses": Member.STATUS_CHOICES,
        }
    )
    return render(request, "koperasi/member_list.html", context)


@koperasi_write_required
def member_create(request):
    form = MemberForm(
        request.POST or None,
        companies=request.koperasi_companies,
        include_user=False,
    )
    if request.method == "POST" and form.is_valid():
        member = form.save(commit=False)
        member.status = "pending"
        member.save()
        _log(request, "MEMBER_CREATED", "Mendaftarkan anggota koperasi.", member)
        messages.success(
            request,
            "Pengajuan anggota berhasil dicatat dan menunggu persetujuan.",
        )
        return redirect("koperasi:member_detail", pk=member.pk)
    context = _base_context(request)
    context.update({"form": form, "form_title": "Tambah Anggota"})
    return render(request, "koperasi/form.html", context)


@koperasi_required
def member_detail(request, pk):
    member = get_object_or_404(_scoped_members(request), pk=pk)
    context = _base_context(request)
    context.update(
        {
            "member": member,
            "principal_balance": member.saving_balance("principal"),
            "mandatory_balance": member.saving_balance("mandatory"),
            "voluntary_balance": member.saving_balance("voluntary"),
            "transactions": member.saving_transactions.all()[:20],
            "loans": member.loans.all(),
        }
    )
    return render(request, "koperasi/member_detail.html", context)


@koperasi_write_required
def member_edit(request, pk):
    member = get_object_or_404(_scoped_members(request), pk=pk)
    form = MemberForm(
        request.POST or None,
        instance=member,
        companies=request.koperasi_companies,
    )
    if request.method == "POST" and form.is_valid():
        member = form.save()
        _log(request, "MEMBER_UPDATED", "Memperbarui data anggota.", member)
        messages.success(request, "Data anggota berhasil diperbarui.")
        return redirect("koperasi:member_detail", pk=member.pk)
    context = _base_context(request)
    context.update(
        {
            "form": form,
            "form_title": "Edit Anggota",
            "delete_url": "koperasi:member_delete",
            "delete_object_pk": member.pk,
            "delete_label": "Hapus Anggota",
        }
    )
    return render(request, "koperasi/form.html", context)


@require_http_methods(["GET", "POST"])
@koperasi_write_required
def member_delete(request, pk):
    member = get_object_or_404(_scoped_members(request), pk=pk)
    related_records = {
        "transaksi simpanan": member.saving_transactions.count(),
        "pinjaman": member.loans.count(),
        "potongan payroll": member.payroll_deductions.count(),
        "transaksi usaha": member.business_transactions.count(),
    }
    blocking_records = {label: count for label, count in related_records.items() if count}

    if request.method == "POST":
        if blocking_records:
            messages.error(
                request,
                "Anggota tidak dapat dihapus karena sudah memiliki riwayat transaksi. "
                "Ubah status anggota menjadi Tidak Aktif atau Keluar.",
            )
            return redirect("koperasi:member_edit", pk=member.pk)

        member_label = str(member)
        _log(request, "MEMBER_DELETED", f"Menghapus anggota {member_label}.", member)
        member.delete()
        messages.success(request, f"Anggota {member_label} berhasil dihapus.")
        return redirect("koperasi:members")

    context = _base_context(request)
    context.update(
        {
            "member": member,
            "blocking_records": blocking_records,
        }
    )
    return render(request, "koperasi/member_confirm_delete.html", context)


@require_POST
@koperasi_required
def member_status(request, pk, action):
    member = get_object_or_404(_scoped_members(request), pk=pk)
    roles = request.koperasi_roles
    if not (
        request.user.is_superuser
        or roles.intersection({"admin", "manager", "chairman", "savings_treasurer"})
    ):
        raise PermissionDenied("Anda tidak berwenang menyetujui anggota.")

    if member.status != "pending" or action not in {"approve", "reject"}:
        messages.error(request, "Perubahan status anggota tidak diizinkan.")
        return redirect("koperasi:member_detail", pk=member.pk)

    if action == "approve":
        member.status = "active"
        member.approved_at = timezone.now()
        member.approved_by = request.user
        action_name = "MEMBER_APPROVED"
        message = "Pengajuan anggota disetujui."
    else:
        member.status = "rejected"
        action_name = "MEMBER_REJECTED"
        message = "Pengajuan anggota ditolak."
    member.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])
    _log(request, action_name, message, member)
    messages.success(request, message)
    return redirect("koperasi:member_detail", pk=member.pk)


@koperasi_required
def saving_list(request):
    selected_view = request.GET.get("view", "list").strip()
    if selected_view not in {"list", "table"}:
        selected_view = "list"
    transactions = SavingTransaction.objects.select_related(
        "member", "member__company", "created_by"
    ).filter(member__company__in=request.koperasi_companies)
    selected_company = _selected_company(request)
    selected_direction = request.GET.get("direction", "").strip()
    selected_saving_type = request.GET.get("saving_type", "").strip()
    if selected_company:
        transactions = transactions.filter(member__company=selected_company)
    if selected_direction in dict(SavingTransaction.DIRECTION_CHOICES):
        transactions = transactions.filter(direction=selected_direction)
    else:
        selected_direction = ""
    if selected_saving_type in dict(SavingTransaction.TYPE_CHOICES):
        transactions = transactions.filter(saving_type=selected_saving_type)
    else:
        selected_saving_type = ""

    try:
        selected_year = int(request.GET.get("year", date.today().year))
    except (TypeError, ValueError):
        selected_year = date.today().year
    if selected_year < 2000 or selected_year > 2100:
        selected_year = date.today().year

    summary_companies = request.koperasi_companies.filter(is_active=True)
    if selected_company:
        summary_companies = summary_companies.filter(pk=selected_company.pk)
    summary_transactions = SavingTransaction.objects.filter(
        member__company__in=summary_companies,
        transaction_date__year=selected_year,
    )
    balances = {}
    for row in summary_transactions:
        key = (row.member_id, row.saving_type)
        signed_amount = row.amount if row.direction == "deposit" else -row.amount
        balances[key] = balances.get(key, Decimal("0")) + signed_amount

    saving_books = []
    for company in summary_companies.order_by("name"):
        member_rows = []
        totals = {
            "principal": Decimal("0"),
            "mandatory": Decimal("0"),
            "voluntary": Decimal("0"),
            "total": Decimal("0"),
        }
        for number, member in enumerate(
            company.members.filter(status="active").order_by("full_name"),
            start=1,
        ):
            principal = balances.get((member.pk, "principal"), Decimal("0"))
            mandatory = balances.get((member.pk, "mandatory"), Decimal("0"))
            voluntary = balances.get((member.pk, "voluntary"), Decimal("0"))
            total_amount = principal + mandatory + voluntary
            totals["principal"] += principal
            totals["mandatory"] += mandatory
            totals["voluntary"] += voluntary
            totals["total"] += total_amount
            member_rows.append(
                {
                    "number": number,
                    "member": member,
                    "principal": principal,
                    "mandatory": mandatory,
                    "voluntary": voluntary,
                    "total": total_amount,
                }
            )
        saving_books.append(
            {"company": company, "member_rows": member_rows, "totals": totals}
        )

    year_values = {date.today().year, selected_year}
    year_values.update(
        SavingTransaction.objects.filter(
            member__company__in=request.koperasi_companies
        ).values_list("transaction_date__year", flat=True).distinct()
    )
    context = _base_context(request)
    context.update(
        {
            "selected_view": selected_view,
            "transactions": transactions[:250],
            "companies": request.koperasi_companies,
            "selected_company": selected_company,
            "directions": SavingTransaction.DIRECTION_CHOICES,
            "selected_direction": selected_direction,
            "saving_types": SavingTransaction.TYPE_CHOICES,
            "selected_saving_type": selected_saving_type,
            "saving_books": saving_books,
            "selected_year": selected_year,
            "years": sorted(year_values, reverse=True),
        }
    )
    return render(request, "koperasi/saving_list.html", context)


@koperasi_write_required
def saving_create(request):
    members = _scoped_members(request)
    form = SavingTransactionForm(request.POST or None, members=members)
    if request.method == "POST" and form.is_valid():
        transaction_row = form.save(commit=False)
        transaction_row.created_by = request.user
        transaction_row.save()
        _log(
            request,
            "SAVING_TRANSACTION_CREATED",
            f"{transaction_row.get_direction_display()} "
            f"{transaction_row.get_saving_type_display()}.",
            transaction_row,
        )
        messages.success(request, "Transaksi simpanan berhasil dicatat.")
        return redirect("koperasi:savings")
    context = _base_context(request)
    context.update({"form": form, "form_title": "Catat Transaksi Simpanan"})
    return render(request, "koperasi/form.html", context)


@koperasi_required
def saving_detail(request, pk):
    transaction_row = get_object_or_404(
        SavingTransaction.objects.select_related(
            "member", "member__company", "created_by"
        ).filter(member__company__in=request.koperasi_companies),
        pk=pk,
    )
    context = _base_context(request)
    context.update({"transaction": transaction_row})
    return render(request, "koperasi/saving_detail.html", context)


@koperasi_write_required
def saving_edit(request, pk):
    transaction_row = get_object_or_404(
        SavingTransaction.objects.select_related("member", "member__company").filter(
            member__company__in=request.koperasi_companies
        ),
        pk=pk,
    )
    form = SavingTransactionForm(
        request.POST or None,
        instance=transaction_row,
        members=_scoped_members(request),
    )
    if request.method == "POST" and form.is_valid():
        transaction_row = form.save()
        _log(
            request,
            "SAVING_TRANSACTION_UPDATED",
            f"Memperbarui transaksi simpanan {transaction_row.transaction_number}.",
            transaction_row,
        )
        messages.success(request, "Transaksi simpanan berhasil diperbarui.")
        return redirect("koperasi:saving_detail", pk=transaction_row.pk)
    context = _base_context(request)
    context.update(
        {
            "form": form,
            "form_title": "Edit Transaksi Simpanan",
            "delete_url": "koperasi:saving_delete",
            "delete_object_pk": transaction_row.pk,
            "delete_label": "Hapus Transaksi",
            "cancel_url": "koperasi:saving_detail",
            "cancel_object_pk": transaction_row.pk,
        }
    )
    return render(request, "koperasi/form.html", context)


@require_http_methods(["GET", "POST"])
@koperasi_write_required
def saving_delete(request, pk):
    transaction_row = get_object_or_404(
        SavingTransaction.objects.select_related("member", "member__company").filter(
            member__company__in=request.koperasi_companies
        ),
        pk=pk,
    )
    if request.method == "POST":
        transaction_number = transaction_row.transaction_number
        _log(
            request,
            "SAVING_TRANSACTION_DELETED",
            f"Menghapus transaksi simpanan {transaction_number}.",
            transaction_row,
        )
        transaction_row.delete()
        messages.success(
            request,
            f"Transaksi simpanan {transaction_number} berhasil dihapus.",
        )
        return redirect("koperasi:savings")

    context = _base_context(request)
    context.update({"transaction": transaction_row})
    return render(request, "koperasi/saving_confirm_delete.html", context)


@koperasi_required
def loan_list(request):
    selected_view = request.GET.get("view", "list").strip()
    if selected_view not in {"list", "table"}:
        selected_view = "list"
    loans = _scoped_loans(request)
    selected_company = _selected_company(request)
    status = request.GET.get("status", "").strip()
    if selected_company:
        loans = loans.filter(member__company=selected_company)
    if status in dict(Loan.STATUS_CHOICES):
        loans = loans.filter(status=status)
    else:
        status = ""
    try:
        selected_year = int(request.GET.get("year", date.today().year))
    except (TypeError, ValueError):
        selected_year = date.today().year
    if selected_year < 2000 or selected_year > 2100:
        selected_year = date.today().year

    summary_companies = request.koperasi_companies.filter(is_active=True)
    if selected_company:
        summary_companies = summary_companies.filter(pk=selected_company.pk)
    summary_loans = Loan.objects.select_related("member").prefetch_related(
        "installments"
    ).filter(
        member__company__in=summary_companies,
        application_date__year=selected_year,
    )
    if status:
        summary_loans = summary_loans.filter(status=status)
    loan_books = []
    for company in summary_companies.order_by("name"):
        loan_rows = []
        totals = {
            "principal": Decimal("0"),
            "paid": Decimal("0"),
            "outstanding": Decimal("0"),
        }
        for number, loan in enumerate(
            summary_loans.filter(member__company=company), start=1
        ):
            paid = loan.amount_paid
            outstanding = loan.outstanding_amount
            totals["principal"] += loan.principal_amount
            totals["paid"] += paid
            totals["outstanding"] += outstanding
            loan_rows.append(
                {
                    "number": number,
                    "loan": loan,
                    "paid": paid,
                    "outstanding": outstanding,
                }
            )
        loan_books.append(
            {"company": company, "loan_rows": loan_rows, "totals": totals}
        )
    year_values = {date.today().year, selected_year}
    year_values.update(
        Loan.objects.filter(
            member__company__in=request.koperasi_companies
        ).values_list("application_date__year", flat=True).distinct()
    )
    context = _base_context(request)
    context.update(
        {
            "selected_view": selected_view,
            "loans": loans,
            "companies": request.koperasi_companies,
            "selected_company": selected_company,
            "statuses": Loan.STATUS_CHOICES,
            "selected_status": status,
            "loan_books": loan_books,
            "selected_year": selected_year,
            "years": sorted(year_values, reverse=True),
        }
    )
    return render(request, "koperasi/loan_list.html", context)


@koperasi_write_required
def loan_create(request):
    form = LoanForm(request.POST or None, members=_scoped_members(request))
    if request.method == "POST" and form.is_valid():
        loan = form.save(commit=False)
        loan.created_by = request.user
        loan.status = "submitted"
        loan.save()
        _log(request, "LOAN_SUBMITTED", "Mencatat pengajuan pinjaman.", loan)
        messages.success(request, "Pengajuan pinjaman berhasil dicatat.")
        return redirect("koperasi:loan_detail", pk=loan.pk)
    context = _base_context(request)
    context.update({"form": form, "form_title": "Pengajuan Pinjaman"})
    return render(request, "koperasi/form.html", context)


@koperasi_required
def loan_detail(request, pk):
    loan = get_object_or_404(_scoped_loans(request), pk=pk)
    context = _base_context(request)
    roles = request.koperasi_roles
    can_record_approval = request.user.is_superuser or bool(
        roles.intersection({"admin", "manager"})
        or ("chairman" in roles and not loan.chairman_approved_at)
        or (
            "savings_treasurer" in roles
            and not loan.savings_treasurer_approved_at
        )
    )
    context.update(
        {
            "loan": loan,
            "installments": loan.installments.all(),
            "can_record_loan_approval": can_record_approval,
        }
    )
    return render(request, "koperasi/loan_detail.html", context)


@koperasi_required
def loan_book(request, pk):
    loan = get_object_or_404(_scoped_loans(request), pk=pk)
    balance = loan.total_due
    ledger_rows = [
        {
            "date": loan.disbursed_date or loan.application_date,
            "description": f"Pencairan pinjaman {loan.loan_number}",
            "debit": loan.total_due,
            "credit": Decimal("0"),
            "balance": balance,
        }
    ]
    for installment in loan.installments.order_by("payment_date", "pk"):
        credit = installment.principal_amount + installment.interest_amount
        balance = max(balance - credit, Decimal("0"))
        description = f"Angsuran {installment.payment_number}"
        if installment.reference:
            description += f" - {installment.reference}"
        if installment.penalty_amount:
            description += f" (denda Rp {installment.penalty_amount:,.0f})"
        ledger_rows.append(
            {
                "date": installment.payment_date,
                "description": description,
                "debit": Decimal("0"),
                "credit": credit,
                "balance": balance,
            }
        )
    context = _base_context(request)
    context.update(
        {
            "loan": loan,
            "ledger_rows": ledger_rows,
            "monthly_interest": (
                loan.total_interest / loan.term_months
                if loan.term_months
                else Decimal("0")
            ),
            "monthly_due": (
                loan.total_due / loan.term_months
                if loan.term_months
                else Decimal("0")
            ),
        }
    )
    return render(request, "koperasi/loan_book.html", context)


@require_POST
@koperasi_manage_required
def loan_status(request, pk, action):
    loan = get_object_or_404(_scoped_loans(request), pk=pk)
    roles = request.koperasi_roles
    approval_roles = {"admin", "manager", "chairman", "savings_treasurer"}
    if action in {"approve", "reject"} and not (
        request.user.is_superuser or roles.intersection(approval_roles)
    ):
        raise PermissionDenied("Anda tidak berwenang menyetujui pinjaman.")

    if loan.status == "submitted" and action == "approve":
        now = timezone.now()
        update_fields = []
        if request.user.is_superuser or roles.intersection({"admin", "manager"}):
            loan.chairman_approved_at = now
            loan.chairman_approved_by = request.user
            loan.savings_treasurer_approved_at = now
            loan.savings_treasurer_approved_by = request.user
            update_fields.extend(
                [
                    "chairman_approved_at",
                    "chairman_approved_by",
                    "savings_treasurer_approved_at",
                    "savings_treasurer_approved_by",
                ]
            )
        elif "chairman" in roles:
            loan.chairman_approved_at = now
            loan.chairman_approved_by = request.user
            update_fields.extend(["chairman_approved_at", "chairman_approved_by"])
        elif "savings_treasurer" in roles:
            loan.savings_treasurer_approved_at = now
            loan.savings_treasurer_approved_by = request.user
            update_fields.extend(
                ["savings_treasurer_approved_at", "savings_treasurer_approved_by"]
            )

        if loan.chairman_approved_at and loan.savings_treasurer_approved_at:
            loan.status = "approved"
            loan.approved_at = now
            loan.approved_by = request.user
            update_fields.extend(["status", "approved_at", "approved_by"])
        loan.save(update_fields=list(dict.fromkeys(update_fields + ["updated_at"])))
        _log(request, "LOAN_APPROVAL_RECORDED", "Persetujuan pinjaman dicatat.", loan)
        messages.success(
            request,
            "Pinjaman disetujui."
            if loan.status == "approved"
            else "Persetujuan dicatat; masih menunggu persetujuan pejabat lainnya.",
        )
        return redirect("koperasi:loan_detail", pk=loan.pk)

    transitions = {
        ("submitted", "reject"): "rejected",
        ("approved", "disburse"): "active",
        ("submitted", "cancel"): "cancelled",
        ("approved", "cancel"): "cancelled",
    }
    new_status = transitions.get((loan.status, action))
    if not new_status:
        messages.error(request, "Perubahan status tersebut tidak diizinkan.")
        return redirect("koperasi:loan_detail", pk=loan.pk)
    loan.status = new_status
    if new_status == "active":
        loan.disbursed_date = date.today()
    loan.save()
    _log(
        request,
        f"LOAN_{new_status.upper()}",
        f"Status pinjaman diubah menjadi {loan.get_status_display()}.",
        loan,
    )
    messages.success(
        request, f"Status pinjaman menjadi {loan.get_status_display()}."
    )
    return redirect("koperasi:loan_detail", pk=loan.pk)


@koperasi_write_required
def installment_create(request, pk):
    loan = get_object_or_404(_scoped_loans(request), pk=pk, status="active")
    form = LoanInstallmentForm(request.POST or None, loan=loan)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked_loan = Loan.objects.select_for_update().get(pk=loan.pk)
            payment = form.save(commit=False)
            payment.loan = locked_loan
            payment.received_by = request.user
            payment.save()
            if locked_loan.outstanding_amount <= Decimal("0"):
                locked_loan.status = "paid"
                locked_loan.save(update_fields=["status", "updated_at"])
        _log(request, "INSTALLMENT_CREATED", "Mencatat angsuran pinjaman.", payment)
        messages.success(request, "Pembayaran angsuran berhasil dicatat.")
        return redirect("koperasi:loan_detail", pk=loan.pk)
    context = _base_context(request)
    context.update(
        {
            "form": form,
            "form_title": f"Bayar Angsuran {loan.loan_number}",
            "loan": loan,
        }
    )
    return render(request, "koperasi/form.html", context)


@koperasi_required
def cash_list(request):
    selected_company = _selected_company(request)
    companies = request.koperasi_companies
    if selected_company:
        companies = companies.filter(pk=selected_company.pk)

    try:
        selected_year = int(request.GET.get("year", date.today().year))
    except (TypeError, ValueError):
        selected_year = date.today().year
    if selected_year < 2000 or selected_year > 2100:
        selected_year = date.today().year

    try:
        selected_month = int(request.GET.get("month", "") or 0)
    except (TypeError, ValueError):
        selected_month = 0
    if selected_month not in range(1, 13):
        selected_month = 0

    selected_unit = request.GET.get("unit", "").strip()
    if selected_unit not in dict(CashTransaction.UNIT_CHOICES):
        selected_unit = ""

    all_rows = _cash_bank_ledger(companies, selected_unit)
    period_start = date(selected_year, selected_month or 1, 1)
    if selected_month == 12:
        period_after = date(selected_year + 1, 1, 1)
    elif selected_month:
        period_after = date(selected_year, selected_month + 1, 1)
    else:
        period_after = date(selected_year + 1, 1, 1)

    opening_cash = Decimal("0")
    opening_bank = Decimal("0")
    for row in all_rows:
        if row["date"] < period_start:
            opening_cash += row["cash_debit"] - row["cash_credit"]
            opening_bank += row["bank_debit"] - row["bank_credit"]

    rows = [row for row in all_rows if period_start <= row["date"] < period_after]
    running_cash = opening_cash
    running_bank = opening_bank
    totals = {
        "cash_debit": Decimal("0"),
        "cash_credit": Decimal("0"),
        "bank_debit": Decimal("0"),
        "bank_credit": Decimal("0"),
    }
    for row in rows:
        for key in totals:
            totals[key] += row[key]
        running_cash += row["cash_debit"] - row["cash_credit"]
        running_bank += row["bank_debit"] - row["bank_credit"]
        row["running_balance"] = running_cash + running_bank

    month_options = [
        (1, "Januari"), (2, "Februari"), (3, "Maret"),
        (4, "April"), (5, "Mei"), (6, "Juni"),
        (7, "Juli"), (8, "Agustus"), (9, "September"),
        (10, "Oktober"), (11, "November"), (12, "Desember"),
    ]
    year_values = {date.today().year, selected_year}
    year_values.update(row["date"].year for row in all_rows)
    context = _base_context(request)
    context.update(
        {
            "ledger_rows": rows,
            "companies": request.koperasi_companies,
            "selected_company": selected_company,
            "selected_year": selected_year,
            "selected_month": selected_month,
            "selected_unit": selected_unit,
            "years": sorted(year_values, reverse=True),
            "months": month_options,
            "units": CashTransaction.UNIT_CHOICES,
            "opening_cash": opening_cash,
            "opening_bank": opening_bank,
            "closing_cash": running_cash,
            "closing_bank": running_bank,
            "totals": totals,
        }
    )
    return render(request, "koperasi/cash_list.html", context)


@koperasi_write_required
def cash_create(request):
    messages.info(
        request,
        "Buku Kas & Bank sekarang terisi otomatis dari transaksi operasional.",
    )
    return redirect("koperasi:cash")


@koperasi_required
def cash_detail(request, pk):
    cash_row = get_object_or_404(
        CashTransaction.objects.select_related("company", "created_by").filter(
            company__in=request.koperasi_companies
        ),
        pk=pk,
    )
    context = _base_context(request)
    context["transaction"] = cash_row
    return render(request, "koperasi/cash_detail.html", context)


@koperasi_required
def cash_voucher(request, source_type, pk):
    companies = request.koperasi_companies
    if source_type == "saving":
        source = get_object_or_404(
            SavingTransaction.objects.select_related("member", "member__company"),
            pk=pk,
            member__company__in=companies,
        )
        account = _ledger_account(reference=source.reference)
        direction = "income" if source.direction == "deposit" else "expense"
        voucher = {
            "number": source.transaction_number,
            "date": source.transaction_date,
            "unit": "SIE SIMPAN PINJAM",
            "account": account,
            "direction": direction,
            "category": source.get_saving_type_display(),
            "description": f"{source.get_direction_display()} {source.get_saving_type_display()} a/n {source.member.full_name}",
            "counterparty": source.member.full_name,
            "amount": source.amount,
        }
    elif source_type == "loan":
        source = get_object_or_404(
            Loan.objects.select_related("member", "member__company"),
            pk=pk,
            member__company__in=companies,
            disbursed_date__isnull=False,
        )
        voucher = {
            "number": source.loan_number,
            "date": source.disbursed_date,
            "unit": "SIE SIMPAN PINJAM",
            "account": _ledger_account(source.payment_method),
            "direction": "expense",
            "category": "Pinjaman anggota",
            "description": f"Pencairan pinjaman {source.loan_number} a/n {source.member.full_name}",
            "counterparty": source.member.full_name,
            "amount": source.principal_amount,
        }
    elif source_type == "installment":
        source = get_object_or_404(
            LoanInstallment.objects.select_related("loan", "loan__member", "loan__member__company"),
            pk=pk,
            loan__member__company__in=companies,
        )
        voucher = {
            "number": source.payment_number,
            "date": source.payment_date,
            "unit": "SIE SIMPAN PINJAM",
            "account": _ledger_account(source.loan.payment_method, source.reference),
            "direction": "income",
            "category": "Angsuran pinjaman",
            "description": f"Pembayaran angsuran {source.loan.loan_number} a/n {source.loan.member.full_name}",
            "counterparty": source.loan.member.full_name,
            "amount": source.total_amount,
        }
    elif source_type == "business":
        source = get_object_or_404(
            BusinessTransaction.objects.select_related("company", "member"),
            pk=pk,
            company__in=companies,
            status__in={"approved", "completed"},
        )
        voucher = {
            "number": source.transaction_number,
            "date": source.transaction_date,
            "unit": "SIE USAHA",
            "account": _ledger_account(source.payment_method),
            "direction": source.direction,
            "category": source.get_activity_type_display(),
            "description": source.description,
            "counterparty": source.member.full_name if source.member else "",
            "amount": source.total_amount,
        }
    elif source_type == "cash":
        source = get_object_or_404(
            CashTransaction.objects.select_related("company"),
            pk=pk,
            company__in=companies,
        )
        voucher = {
            "number": source.transaction_number,
            "date": source.transaction_date,
            "unit": source.get_unit_display().upper(),
            "account": source.account,
            "direction": source.transaction_type,
            "category": source.category,
            "description": source.description,
            "counterparty": source.counterparty,
            "amount": source.amount,
        }
    else:
        raise Http404("Sumber transaksi tidak ditemukan.")

    account_label = "Kas" if voucher["account"] == "cash" else "Bank"
    direction_label = "Masuk" if voucher["direction"] == "income" else "Keluar"
    voucher["title"] = f"{account_label} {direction_label}"
    voucher["amount_words"] = _terbilang(voucher["amount"])
    context = _base_context(request)
    context["voucher"] = voucher
    return render(request, "koperasi/cash_voucher.html", context)


@koperasi_required
def payroll_list(request):
    selected_view = request.GET.get("view", "list").strip()
    if selected_view not in {"list", "table"}:
        selected_view = "list"
    selected_company = _selected_company(request)
    legacy_period = request.GET.get("period", "").strip()
    try:
        selected_year = int(request.GET.get("year", date.today().year))
    except (TypeError, ValueError):
        selected_year = date.today().year
    try:
        selected_month = int(request.GET.get("month", date.today().month))
    except (TypeError, ValueError):
        selected_month = date.today().month
    if len(legacy_period) == 7 and legacy_period[:4].isdigit() and legacy_period[5:].isdigit():
        selected_year = int(legacy_period[:4])
        selected_month = int(legacy_period[5:])
    if selected_year < 2000 or selected_year > 2100:
        selected_year = date.today().year
    if selected_month not in range(1, 13):
        selected_month = date.today().month

    companies = request.koperasi_companies.filter(is_active=True)
    if selected_company:
        companies = companies.filter(pk=selected_company.pk)
    deductions = PayrollDeduction.objects.select_related("member").filter(
        member__company__in=companies,
        period__year=selected_year,
        period__month=selected_month,
    )
    deductions_by_member = {row.member_id: row for row in deductions}
    company_books = []
    for company in companies.order_by("name"):
        member_rows = []
        totals = {
            "principal": Decimal("0"),
            "mandatory": Decimal("0"),
            "voluntary": Decimal("0"),
            "loan": Decimal("0"),
            "total": Decimal("0"),
        }
        members = company.members.filter(status="active").order_by("full_name")
        for number, member in enumerate(members, start=1):
            deduction = deductions_by_member.get(member.pk)
            principal = deduction.principal_saving if deduction else Decimal("0")
            mandatory = deduction.mandatory_saving if deduction else Decimal("0")
            voluntary = deduction.voluntary_saving if deduction else Decimal("0")
            loan_amount = (
                deduction.loan_principal + deduction.loan_interest
                if deduction
                else Decimal("0")
            )
            total_amount = principal + mandatory + voluntary + loan_amount
            totals["principal"] += principal
            totals["mandatory"] += mandatory
            totals["voluntary"] += voluntary
            totals["loan"] += loan_amount
            totals["total"] += total_amount
            member_rows.append(
                {
                    "number": number,
                    "member": member,
                    "deduction": deduction,
                    "principal": principal,
                    "mandatory": mandatory,
                    "voluntary": voluntary,
                    "loan": loan_amount,
                    "total": total_amount,
                }
            )
        company_books.append(
            {"company": company, "member_rows": member_rows, "totals": totals}
        )

    year_values = {date.today().year, selected_year}
    year_values.update(
        PayrollDeduction.objects.filter(
            member__company__in=request.koperasi_companies
        ).values_list("period__year", flat=True).distinct()
    )
    month_options = [
        (1, "Januari"), (2, "Februari"), (3, "Maret"),
        (4, "April"), (5, "Mei"), (6, "Juni"),
        (7, "Juli"), (8, "Agustus"), (9, "September"),
        (10, "Oktober"), (11, "November"), (12, "Desember"),
    ]
    context = _base_context(request)
    context.update(
        {
            "selected_view": selected_view,
            "deductions": deductions.order_by("member__company__name", "member__full_name"),
            "company_books": company_books,
            "companies": request.koperasi_companies,
            "selected_company": selected_company,
            "selected_year": selected_year,
            "selected_month": selected_month,
            "years": sorted(year_values, reverse=True),
            "months": month_options,
        }
    )
    return render(request, "koperasi/payroll_list.html", context)


@koperasi_write_required
def payroll_create(request):
    form = PayrollDeductionForm(
        request.POST or None,
        members=_scoped_members(request),
    )
    if request.method == "POST" and form.is_valid():
        deduction = form.save(commit=False)
        deduction.created_by = request.user
        deduction.save()
        _log(request, "PAYROLL_DEDUCTION_CREATED", "Mencatat potongan payroll.", deduction)
        messages.success(request, "Potongan payroll disimpan sebagai draf.")
        return redirect("koperasi:payroll")
    context = _base_context(request)
    context.update({"form": form, "form_title": "Input Potongan Payroll Bulanan"})
    return render(request, "koperasi/form.html", context)


@require_POST
@koperasi_write_required
def payroll_post(request, pk):
    with transaction.atomic():
        deduction = get_object_or_404(
            PayrollDeduction.objects.select_for_update().select_related("member").filter(
                member__company__in=request.koperasi_companies
            ),
            pk=pk,
        )
        if deduction.status == "posted":
            messages.info(request, "Potongan ini sudah dibukukan.")
            return redirect("koperasi:payroll")

        transaction_date = deduction.period.replace(day=10)
        saving_values = (
            ("principal", deduction.principal_saving, "PKK"),
            ("mandatory", deduction.mandatory_saving, "WJB"),
            ("voluntary", deduction.voluntary_saving, "SKR"),
        )
        for saving_type, amount, suffix in saving_values:
            if amount > 0:
                SavingTransaction.objects.create(
                    transaction_number=f"PAY-{deduction.pk}-{suffix}",
                    member=deduction.member,
                    saving_type=saving_type,
                    direction="deposit",
                    transaction_date=transaction_date,
                    amount=amount,
                    reference=f"Payroll {deduction.period:%m/%Y}",
                    notes=deduction.notes,
                    created_by=request.user,
                )

        loan_payment = deduction.loan_principal + deduction.loan_interest
        if loan_payment > 0:
            active_loan = deduction.member.loans.filter(status="active").first()
            if active_loan is None:
                messages.error(
                    request,
                    "Tidak ada pinjaman aktif untuk membukukan potongan pinjaman.",
                )
                transaction.set_rollback(True)
                return redirect("koperasi:payroll")
            if loan_payment > active_loan.outstanding_amount:
                messages.error(request, "Potongan pinjaman melebihi sisa tagihan.")
                transaction.set_rollback(True)
                return redirect("koperasi:payroll")
            active_loan.installments.create(
                payment_number=f"PAY-{deduction.pk}-PIN",
                payment_date=transaction_date,
                principal_amount=deduction.loan_principal,
                interest_amount=deduction.loan_interest,
                penalty_amount=0,
                reference=f"Payroll {deduction.period:%m/%Y}",
                notes=deduction.notes,
                received_by=request.user,
            )
            if active_loan.outstanding_amount <= 0:
                active_loan.status = "paid"
                active_loan.save(update_fields=["status", "updated_at"])

        deduction.status = "posted"
        deduction.save(update_fields=["status", "updated_at"])

    _log(request, "PAYROLL_DEDUCTION_POSTED", "Membukukan potongan payroll.", deduction)
    messages.success(request, "Potongan payroll berhasil dibukukan.")
    return redirect("koperasi:payroll")


@koperasi_required
def business_list(request):
    selected_view = request.GET.get("view", "list").strip()
    if selected_view not in {"list", "table"}:
        selected_view = "list"
    rows = BusinessTransaction.objects.select_related(
        "company", "member", "created_by", "approved_by"
    ).filter(company__in=request.koperasi_companies)
    selected_company = _selected_company(request)
    selected_activity = request.GET.get("activity", "").strip()
    selected_payment = request.GET.get("payment", "").strip()
    selected_status = request.GET.get("status", "").strip()
    if selected_company:
        rows = rows.filter(company=selected_company)
    if selected_activity in dict(BusinessTransaction.ACTIVITY_CHOICES):
        rows = rows.filter(activity_type=selected_activity)
    else:
        selected_activity = ""
    if selected_payment in dict(BusinessTransaction.PAYMENT_METHOD_CHOICES):
        rows = rows.filter(payment_method=selected_payment)
    else:
        selected_payment = ""
    if selected_status in dict(BusinessTransaction.STATUS_CHOICES):
        rows = rows.filter(status=selected_status)
    else:
        selected_status = ""

    try:
        selected_year = int(request.GET.get("year", date.today().year))
    except (TypeError, ValueError):
        selected_year = date.today().year
    try:
        selected_month = int(request.GET.get("month", 0))
    except (TypeError, ValueError):
        selected_month = 0
    if selected_year < 2000 or selected_year > 2100:
        selected_year = date.today().year
    if selected_month not in range(0, 13):
        selected_month = 0

    summary_rows = rows.filter(transaction_date__year=selected_year)
    if selected_month:
        summary_rows = summary_rows.filter(transaction_date__month=selected_month)
    summary_companies = request.koperasi_companies.filter(is_active=True)
    if selected_company:
        summary_companies = summary_companies.filter(pk=selected_company.pk)
    business_books = []
    for company in summary_companies.order_by("name"):
        activity_rows = []
        company_income = Decimal("0")
        company_expense = Decimal("0")
        company_rows = summary_rows.filter(company=company)
        for activity_value, activity_label in BusinessTransaction.ACTIVITY_CHOICES:
            activity_transactions = list(
                company_rows.filter(activity_type=activity_value)
            )
            if not activity_transactions:
                continue
            income = sum(
                (
                    transaction.total_amount
                    for transaction in activity_transactions
                    if transaction.direction == "income"
                ),
                Decimal("0"),
            )
            expense = sum(
                (
                    transaction.total_amount
                    for transaction in activity_transactions
                    if transaction.direction == "expense"
                ),
                Decimal("0"),
            )
            company_income += income
            company_expense += expense
            activity_rows.append(
                {
                    "label": activity_label,
                    "count": len(activity_transactions),
                    "income": income,
                    "expense": expense,
                    "net": income - expense,
                }
            )
        business_books.append(
            {
                "company": company,
                "activity_rows": activity_rows,
                "totals": {
                    "income": company_income,
                    "expense": company_expense,
                    "net": company_income - company_expense,
                },
            }
        )

    year_values = {date.today().year, selected_year}
    year_values.update(
        value
        for value in BusinessTransaction.objects.filter(
            company__in=request.koperasi_companies
        ).values_list("transaction_date__year", flat=True).distinct()
        if value is not None
    )
    month_options = [
        (0, "Semua bulan"),
        (1, "Januari"), (2, "Februari"), (3, "Maret"),
        (4, "April"), (5, "Mei"), (6, "Juni"),
        (7, "Juli"), (8, "Agustus"), (9, "September"),
        (10, "Oktober"), (11, "November"), (12, "Desember"),
    ]
    context = _base_context(request)
    context.update(
        {
            "selected_view": selected_view,
            "transactions": rows[:500],
            "business_books": business_books,
            "companies": request.koperasi_companies,
            "selected_company": selected_company,
            "activities": BusinessTransaction.ACTIVITY_CHOICES,
            "selected_activity": selected_activity,
            "payment_methods": BusinessTransaction.PAYMENT_METHOD_CHOICES,
            "selected_payment": selected_payment,
            "statuses": BusinessTransaction.STATUS_CHOICES,
            "selected_status": selected_status,
            "selected_year": selected_year,
            "selected_month": selected_month,
            "years": sorted(year_values, reverse=True),
            "months": month_options,
        }
    )
    return render(request, "koperasi/business_list.html", context)


@koperasi_write_required
def business_create(request):
    form = BusinessTransactionForm(
        request.POST or None,
        companies=request.koperasi_companies,
        members=_scoped_members(request),
    )
    if request.method == "POST" and form.is_valid():
        business_row = form.save(commit=False)
        business_row.created_by = request.user
        business_row.status = "submitted"
        business_row.save()
        _log(request, "BUSINESS_TRANSACTION_SUBMITTED", "Mencatat transaksi Sie Usaha.", business_row)
        messages.success(request, "Transaksi Sie Usaha diajukan untuk persetujuan.")
        return redirect("koperasi:business")
    context = _base_context(request)
    context.update({"form": form, "form_title": "Input Transaksi Sie Usaha"})
    return render(request, "koperasi/form.html", context)


@require_POST
@koperasi_required
def business_status(request, pk, action):
    business_row = get_object_or_404(
        BusinessTransaction.objects.filter(company__in=request.koperasi_companies),
        pk=pk,
    )
    roles = request.koperasi_roles
    can_approve = request.user.is_superuser or bool(
        roles.intersection(
            {"admin", "manager", "chairman", "business_treasurer"}
        )
    )
    if action in {"approve", "reject"} and not can_approve:
        raise PermissionDenied("Anda tidak berwenang menyetujui transaksi Sie Usaha.")

    transitions = {
        ("submitted", "approve"): "approved",
        ("submitted", "reject"): "rejected",
        ("approved", "complete"): "completed",
    }
    new_status = transitions.get((business_row.status, action))
    if new_status is None:
        messages.error(request, "Perubahan status transaksi tidak diizinkan.")
        return redirect("koperasi:business")
    if action == "complete" and not (
        can_approve or roles.intersection({"treasurer", "officer", "finance"})
    ):
        raise PermissionDenied("Anda tidak berwenang menyelesaikan transaksi.")

    business_row.status = new_status
    if new_status == "approved":
        business_row.approved_at = timezone.now()
        business_row.approved_by = request.user
    business_row.save()
    _log(
        request,
        f"BUSINESS_{new_status.upper()}",
        f"Status transaksi Sie Usaha menjadi {business_row.get_status_display()}.",
        business_row,
    )
    messages.success(request, "Status transaksi Sie Usaha diperbarui.")
    return redirect("koperasi:business")


@koperasi_admin_required
def access_list(request):
    rows = KoperasiAccess.objects.select_related("user", "company").filter(
        Q(company__in=request.koperasi_companies) | Q(company__isnull=True)
    )
    context = _base_context(request)
    context["access_rows"] = rows
    return render(request, "koperasi/access_list.html", context)


@koperasi_admin_required
def access_create(request):
    form = KoperasiAccessForm(request.POST or None)
    form.fields["company"].queryset = request.koperasi_companies
    if request.method == "POST" and form.is_valid():
        access = form.save()
        _log(request, "ACCESS_CREATED", "Memberikan akses Sistem Koperasi.", access)
        messages.success(request, "Hak akses berhasil ditambahkan.")
        return redirect("koperasi:access")
    context = _base_context(request)
    context.update({"form": form, "form_title": "Tambah Hak Akses"})
    return render(request, "koperasi/form.html", context)


@koperasi_required
def report(request):
    try:
        year = int(request.GET.get("year", date.today().year))
    except (TypeError, ValueError):
        year = date.today().year
    if year < 2000 or year > 2100:
        year = date.today().year

    period_start = date(year, 1, 1)
    period_end = date(year, 12, 31)
    companies = request.koperasi_companies
    selected_company = _selected_company(request)
    if selected_company:
        companies = companies.filter(pk=selected_company.pk)

    members = Member.objects.filter(company__in=companies)
    savings = SavingTransaction.objects.filter(
        member__in=members,
        transaction_date__lte=period_end,
    )
    loans = Loan.objects.filter(member__in=members, application_date__lte=period_end)
    cash_to_date = CashTransaction.objects.filter(
        company__in=companies,
        transaction_date__lte=period_end,
    )
    cash_period = cash_to_date.filter(transaction_date__gte=period_start)
    business_period = BusinessTransaction.objects.filter(
        company__in=companies,
        transaction_date__range=(period_start, period_end),
        status__in={"approved", "completed"},
    )

    def amount_sum(queryset, field="amount"):
        return queryset.aggregate(total=Coalesce(Sum(field), Decimal("0")))["total"]

    saving_balances = {}
    for saving_type, _label in SavingTransaction.TYPE_CHOICES:
        typed = savings.filter(saving_type=saving_type)
        saving_balances[saving_type] = amount_sum(
            typed.filter(direction="deposit")
        ) - amount_sum(typed.filter(direction="withdrawal"))
    total_savings = sum(saving_balances.values(), Decimal("0"))

    ledger_to_date = [
        row for row in _cash_bank_ledger(companies) if row["date"] <= period_end
    ]
    cash_balance = sum(
        (row["cash_debit"] - row["cash_credit"] for row in ledger_to_date),
        Decimal("0"),
    )
    bank_balance = sum(
        (row["bank_debit"] - row["bank_credit"] for row in ledger_to_date),
        Decimal("0"),
    )
    loan_receivables = sum(
        (loan.outstanding_amount for loan in loans.exclude(status__in={"rejected", "cancelled"})),
        Decimal("0"),
    )

    cash_income = amount_sum(cash_period.filter(transaction_type="income"))
    cash_expense = amount_sum(cash_period.filter(transaction_type="expense"))
    business_income = sum(
        (row.total_amount for row in business_period.filter(direction="income")),
        Decimal("0"),
    )
    business_expense = sum(
        (row.total_amount for row in business_period.filter(direction="expense")),
        Decimal("0"),
    )
    loan_interest_income = amount_sum(
        loans.filter(installments__payment_date__range=(period_start, period_end)),
        "installments__interest_amount",
    )
    operating_income = cash_income + business_income + loan_interest_income
    operating_expense = cash_expense + business_expense
    shu = operating_income - operating_expense
    total_assets = cash_balance + bank_balance + loan_receivables
    reserve_equity = total_assets - total_savings

    member_rows = []
    for member in members.filter(status="active").order_by("full_name"):
        member_savings = member.saving_balance()
        interest_paid = amount_sum(
            member.loans.filter(
                installments__payment_date__range=(period_start, period_end)
            ),
            "installments__interest_amount",
        )
        member_rows.append(
            {
                "member": member,
                "savings": member_savings,
                "interest": interest_paid,
            }
        )
    total_member_savings = sum((row["savings"] for row in member_rows), Decimal("0"))
    total_member_interest = sum((row["interest"] for row in member_rows), Decimal("0"))
    allocatable_shu = max(shu, Decimal("0"))
    for row in member_rows:
        saving_share = (
            allocatable_shu * Decimal("0.20") * row["savings"] / total_member_savings
            if total_member_savings > 0
            else Decimal("0")
        )
        loan_share = (
            allocatable_shu * Decimal("0.80") * row["interest"] / total_member_interest
            if total_member_interest > 0
            else Decimal("0")
        )
        row["saving_share"] = saving_share.quantize(Decimal("0.01"))
        row["loan_share"] = loan_share.quantize(Decimal("0.01"))
        row["total_shu"] = row["saving_share"] + row["loan_share"]

    context = _base_context(request)
    context.update(
        {
            "companies": request.koperasi_companies,
            "selected_company": selected_company,
            "year": year,
            "active_member_count": members.filter(status="active").count(),
            "saving_balances": saving_balances,
            "total_savings": total_savings,
            "active_loan_count": loans.filter(status="active").count(),
            "loan_receivables": loan_receivables,
            "cash_balance": cash_balance,
            "bank_balance": bank_balance,
            "total_assets": total_assets,
            "reserve_equity": reserve_equity,
            "cash_income": cash_income,
            "cash_expense": cash_expense,
            "business_income": business_income,
            "business_expense": business_expense,
            "loan_interest_income": loan_interest_income,
            "operating_income": operating_income,
            "operating_expense": operating_expense,
            "shu": shu,
            "payroll_rows": PayrollDeduction.objects.select_related("member").filter(
                member__in=members,
                period__year=year,
            )[:500],
            "shu_rows": member_rows,
        }
    )
    return render(request, "koperasi/report.html", context)


@koperasi_required
def report_csv(request):
    import csv

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="laporan-koperasi-{date.today().isoformat()}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(
        ["Perusahaan", "Nomor Anggota", "Nama", "Status", "Saldo Simpanan"]
    )
    for member in _scoped_members(request):
        writer.writerow(
            [
                member.company.name,
                member.member_number,
                member.full_name,
                member.get_status_display(),
                member.saving_balance(),
            ]
        )
    return response


@koperasi_required
@never_cache
@require_http_methods(["GET", "POST"])
def bug_report(request):
    form = ReportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        title = form.cleaned_data["title"]
        description = form.cleaned_data["description"]
        steps = form.cleaned_data["steps"]
        screenshot = form.cleaned_data.get("screenshot")
        user = request.user

        email_body = textwrap.dedent(
            f"""
            BUG REPORT - SISTEM KOPERASI

            User: {user.username}
            Email: {user.email}

            Title: {title}

            Description:
            {description}

            Steps:
            {steps}
            """
        ).strip()
        email = EmailMessage(
            subject=f"Report Bug {title} from PWU KOPERASI",
            body=email_body,
            to=[settings.EMAIL_TO_REPORT],
        )
        if screenshot:
            email.attach(
                screenshot.name,
                screenshot.read(),
                screenshot.content_type,
            )
        email.send()
        record_activity(
            request=request,
            category="KOPERASI",
            action="BUG_REPORT_SENT",
            description="Koperasi bug report sent by email.",
            target_type="koperasi.Report",
            target_label=title or "Untitled report",
        )
        messages.success(request, "Report berhasil dikirim.")
        return redirect("koperasi:dashboard")

    context = _base_context(request)
    context["form"] = form
    return render(request, "koperasi/bug_report.html", context)
