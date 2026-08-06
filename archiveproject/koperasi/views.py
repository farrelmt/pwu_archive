from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.audit import record_activity

from .access import (
    APPROVE_ROLES,
    can_manage_global_access,
    koperasi_admin_required,
    koperasi_manage_required,
    koperasi_required,
    koperasi_write_required,
)
from .forms import (
    CashTransactionForm,
    CompanyForm,
    KoperasiAccessForm,
    LoanForm,
    LoanInstallmentForm,
    MemberForm,
    SavingTransactionForm,
)
from .models import (
    CashTransaction,
    Company,
    KoperasiAccess,
    Loan,
    Member,
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
    return {
        "koperasi_roles": roles,
        "can_write": bool(roles.intersection({"admin", "manager", "finance", "officer"})),
        "can_manage": bool(roles.intersection({"admin", "manager"})),
        "can_approve": bool(roles.intersection(APPROVE_ROLES)),
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


@koperasi_required
def dashboard(request):
    companies = request.koperasi_companies.filter(is_active=True)
    members = _scoped_members(request)
    loans = _scoped_loans(request)
    savings = SavingTransaction.objects.filter(member__in=members)
    cash = CashTransaction.objects.filter(company__in=companies)

    deposits = savings.filter(direction="deposit").aggregate(
        value=Coalesce(Sum("amount"), Decimal("0"))
    )["value"]
    withdrawals = savings.filter(direction="withdrawal").aggregate(
        value=Coalesce(Sum("amount"), Decimal("0"))
    )["value"]
    income = cash.filter(transaction_type="income").aggregate(
        value=Coalesce(Sum("amount"), Decimal("0"))
    )["value"]
    expenses = cash.filter(transaction_type="expense").aggregate(
        value=Coalesce(Sum("amount"), Decimal("0"))
    )["value"]

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
            "cash_balance": income - expenses,
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
    )
    if request.method == "POST" and form.is_valid():
        member = form.save()
        _log(request, "MEMBER_CREATED", "Mendaftarkan anggota koperasi.", member)
        messages.success(request, "Anggota berhasil ditambahkan.")
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
    context.update({"form": form, "form_title": "Edit Anggota"})
    return render(request, "koperasi/form.html", context)


@koperasi_required
def saving_list(request):
    transactions = SavingTransaction.objects.select_related(
        "member", "member__company", "created_by"
    ).filter(member__company__in=request.koperasi_companies)
    selected_company = _selected_company(request)
    if selected_company:
        transactions = transactions.filter(member__company=selected_company)
    context = _base_context(request)
    context.update(
        {
            "transactions": transactions[:250],
            "companies": request.koperasi_companies,
            "selected_company": selected_company,
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
def loan_list(request):
    loans = _scoped_loans(request)
    selected_company = _selected_company(request)
    status = request.GET.get("status", "").strip()
    if selected_company:
        loans = loans.filter(member__company=selected_company)
    if status in dict(Loan.STATUS_CHOICES):
        loans = loans.filter(status=status)
    context = _base_context(request)
    context.update(
        {
            "loans": loans,
            "companies": request.koperasi_companies,
            "selected_company": selected_company,
            "statuses": Loan.STATUS_CHOICES,
            "selected_status": status,
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
    context.update({"loan": loan, "installments": loan.installments.all()})
    return render(request, "koperasi/loan_detail.html", context)


@require_POST
@koperasi_manage_required
def loan_status(request, pk, action):
    loan = get_object_or_404(_scoped_loans(request), pk=pk)
    transitions = {
        ("submitted", "approve"): "approved",
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
    if new_status == "approved":
        loan.approved_at = timezone.now()
        loan.approved_by = request.user
    elif new_status == "active":
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
    rows = CashTransaction.objects.select_related("company", "created_by").filter(
        company__in=request.koperasi_companies
    )
    selected_company = _selected_company(request)
    if selected_company:
        rows = rows.filter(company=selected_company)
    context = _base_context(request)
    context.update(
        {
            "transactions": rows[:250],
            "companies": request.koperasi_companies,
            "selected_company": selected_company,
        }
    )
    return render(request, "koperasi/cash_list.html", context)


@koperasi_write_required
def cash_create(request):
    form = CashTransactionForm(
        request.POST or None,
        companies=request.koperasi_companies,
    )
    if request.method == "POST" and form.is_valid():
        cash_row = form.save(commit=False)
        cash_row.created_by = request.user
        cash_row.save()
        _log(request, "CASH_TRANSACTION_CREATED", "Mencatat transaksi kas.", cash_row)
        messages.success(request, "Transaksi kas berhasil dicatat.")
        return redirect("koperasi:cash")
    context = _base_context(request)
    context.update({"form": form, "form_title": "Catat Transaksi Kas"})
    return render(request, "koperasi/form.html", context)


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
    companies = request.koperasi_companies
    selected_company = _selected_company(request)
    if selected_company:
        companies = companies.filter(pk=selected_company.pk)
    rows = []
    for company in companies:
        members = Member.objects.filter(company=company)
        savings = SavingTransaction.objects.filter(member__in=members)
        deposits = savings.filter(direction="deposit").aggregate(
            total=Coalesce(Sum("amount"), Decimal("0"))
        )["total"]
        withdrawals = savings.filter(direction="withdrawal").aggregate(
            total=Coalesce(Sum("amount"), Decimal("0"))
        )["total"]
        loans = Loan.objects.filter(member__in=members)
        rows.append(
            {
                "company": company,
                "members": members.filter(status="active").count(),
                "savings": deposits - withdrawals,
                "active_loans": loans.filter(status="active").count(),
                "loan_principal": loans.filter(status="active").aggregate(
                    total=Coalesce(Sum("principal_amount"), Decimal("0"))
                )["total"],
            }
        )
    context = _base_context(request)
    context.update(
        {
            "rows": rows,
            "companies": request.koperasi_companies,
            "selected_company": selected_company,
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
