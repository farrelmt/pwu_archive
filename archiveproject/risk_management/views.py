from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .access import can_edit_risk, risk_required, risk_write_required, risks_for_user
from .forms import RiskActionPlanForm, RiskMonitoringForm, RiskRegisterForm
from .models import (
    RiskActionPlan,
    RiskActivity,
    RiskDivision,
    RiskMonitoring,
    RiskRegister,
)


def _level_counts(risks):
    counts = {"Rendah": 0, "Sedang": 0, "Tinggi": 0, "Sangat_Tinggi": 0}
    for risk in risks:
        key = "Sangat_Tinggi" if risk.risk_level == "Sangat Tinggi" else risk.risk_level
        counts[key] += 1
    return counts


def _current_period():
    today = timezone.localdate()
    return today.year, ((today.month - 1) // 3) + 1


def _selected_period(request):
    default_year, default_quarter = _current_period()
    try:
        year = int(request.GET.get("year", default_year))
    except (TypeError, ValueError):
        year = default_year
    try:
        quarter = int(request.GET.get("quarter", default_quarter))
    except (TypeError, ValueError):
        quarter = default_quarter
    if not 2020 <= year <= 2100:
        year = default_year
    if quarter not in {1, 2, 3, 4}:
        quarter = default_quarter
    return year, quarter


def _monitoring_summary(monitorings):
    rows_by_division = {}
    totals = {
        "risk_count": 0, "plan_count": 0, "realized_count": 0,
        "initial_score": 0, "final_score": 0, "score_reduction": 0,
    }
    for monitoring in monitorings:
        division = monitoring.risk.division
        row = rows_by_division.setdefault(division.pk, {
            "division": division, "risk_count": 0, "plan_count": 0,
            "realized_count": 0, "initial_score": 0, "final_score": 0,
            "score_reduction": 0,
        })
        plans = list(monitoring.action_plans.all())
        realized = sum(plan.is_realized for plan in plans)
        values = {
            "risk_count": 1,
            "plan_count": len(plans),
            "realized_count": realized,
            "initial_score": monitoring.initial_score,
            "final_score": monitoring.final_score,
            "score_reduction": monitoring.score_reduction,
        }
        for key, value in values.items():
            row[key] += value
            totals[key] += value
    rows = sorted(rows_by_division.values(), key=lambda item: item["division"].name)
    for item in [*rows, totals]:
        item["realization_percent"] = round(
            item["realized_count"] * 100 / item["plan_count"]
        ) if item["plan_count"] else 0
    return rows, totals


@risk_required
def dashboard(request):
    risks = list(risks_for_user(request.user))
    counts = _level_counts(risks)
    year, quarter = _current_period()
    current_monitorings = list(
        RiskMonitoring.objects.filter(
            risk__in=risks_for_user(request.user), year=year, quarter=quarter,
        ).select_related("risk__division").prefetch_related("action_plans")
    )
    division_rows, monitoring_totals = _monitoring_summary(current_monitorings)
    return render(request, "risk_management/dashboard.html", {
        "total_risks": len(risks),
        "open_risks": sum(r.status != "closed" for r in risks),
        "overdue_risks": sum(bool(r.target_date and r.target_date < __import__('datetime').date.today() and r.status != "closed") for r in risks),
        "level_counts": counts,
        "recent_risks": risks[:8],
        "division_count": len({r.division_id for r in risks}),
        "monitoring_year": year,
        "monitoring_quarter": quarter,
        "monitoring_quarter_label": dict(RiskMonitoring.QUARTER_CHOICES)[quarter],
        "monitoring_totals": monitoring_totals,
        "division_rows": division_rows,
    })


@risk_required
def risk_list(request):
    risks = risks_for_user(request.user)
    search = request.GET.get("q", "").strip()
    division = request.GET.get("division", "").strip()
    status = request.GET.get("status", "").strip()
    category = request.GET.get("category", "").strip()
    level = request.GET.get("level", "").strip()
    if search:
        risks = risks.filter(Q(risk_code__icontains=search) | Q(title__icontains=search) | Q(risk_owner__icontains=search))
    if division.isdigit():
        risks = risks.filter(division_id=division)
    if status in dict(RiskRegister.STATUS_CHOICES):
        risks = risks.filter(status=status)
    if category in dict(RiskRegister.CATEGORY_CHOICES):
        risks = risks.filter(category=category)
    if level:
        ids = [risk.pk for risk in risks if risk.risk_level.lower() == level.lower()]
        risks = risks.filter(pk__in=ids)
    page_obj = Paginator(risks, 20).get_page(request.GET.get("page"))
    visible_divisions = RiskDivision.objects.filter(risks__in=risks_for_user(request.user)).distinct()
    return render(request, "risk_management/risk_list.html", {
        "page_obj": page_obj, "divisions": visible_divisions,
        "statuses": RiskRegister.STATUS_CHOICES, "categories": RiskRegister.CATEGORY_CHOICES,
        "filters": {"q": search, "division": division, "status": status, "category": category, "level": level},
    })


@risk_required
def risk_detail(request, pk):
    risk = get_object_or_404(
        risks_for_user(request.user).prefetch_related(
            Prefetch(
                "monitorings",
                queryset=RiskMonitoring.objects.prefetch_related("action_plans").select_related("updated_by"),
            )
        ),
        pk=pk,
    )
    return render(request, "risk_management/risk_detail.html", {
        "risk": risk, "can_edit_this": can_edit_risk(request.user, risk),
    })


@risk_write_required
def risk_create(request):
    form = RiskRegisterForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        risk = form.save(commit=False)
        risk.created_by = request.user
        risk.updated_by = request.user
        risk.save()
        RiskActivity.objects.create(risk=risk, actor=request.user, action="created", description="Risiko dibuat.")
        messages.success(request, f"{risk.risk_code} berhasil ditambahkan.")
        return redirect("risk:risk_detail", pk=risk.pk)
    return render(request, "risk_management/risk_form.html", {"form": form, "page_title": "Tambah Risiko"})


@risk_write_required
def risk_edit(request, pk):
    risk = get_object_or_404(risks_for_user(request.user), pk=pk)
    if not can_edit_risk(request.user, risk):
        raise PermissionDenied("Anda tidak dapat mengubah risiko divisi lain.")
    form = RiskRegisterForm(request.POST or None, instance=risk, user=request.user)
    if request.method == "POST" and form.is_valid():
        risk = form.save(commit=False)
        risk.updated_by = request.user
        risk.save()
        RiskActivity.objects.create(risk=risk, actor=request.user, action="updated", description="Data risiko diperbarui.")
        messages.success(request, f"{risk.risk_code} berhasil diperbarui.")
        return redirect("risk:risk_detail", pk=risk.pk)
    return render(request, "risk_management/risk_form.html", {"form": form, "risk": risk, "page_title": "Edit Risiko"})


@risk_required
def divisions(request):
    access_rows = RiskDivision.objects.prefetch_related("accesses__user")
    if not request.user.is_superuser and not request.risk_accesses.filter(
        role__in={"head_manager", "manager_member"}
    ).exists():
        division_ids = request.risk_accesses.exclude(
            division__isnull=True
        ).values_list("division_id", flat=True)
        access_rows = access_rows.filter(pk__in=division_ids)
    return render(request, "risk_management/divisions.html", {"divisions": access_rows})


@risk_required
def monitoring_report(request):
    year, quarter = _selected_period(request)
    division = request.GET.get("division", "").strip()
    visible_risks = risks_for_user(request.user)
    if division.isdigit():
        visible_risks = visible_risks.filter(division_id=division)
    monitorings = list(
        RiskMonitoring.objects.filter(
            risk__in=visible_risks, year=year, quarter=quarter,
        ).select_related("risk__division").prefetch_related("action_plans")
    )
    division_rows, totals = _monitoring_summary(monitorings)
    priority_risks = sorted(
        [item for item in monitorings if item.final_score >= 12],
        key=lambda item: (-item.final_score, item.risk.risk_code),
    )
    visible_divisions = RiskDivision.objects.filter(
        risks__in=risks_for_user(request.user)
    ).distinct().order_by("name")
    available_years = sorted(
        set(
            RiskMonitoring.objects.filter(risk__in=risks_for_user(request.user))
            .values_list("year", flat=True)
        ) | {year},
        reverse=True,
    )
    return render(request, "risk_management/monitoring_report.html", {
        "year": year,
        "quarter": quarter,
        "quarter_label": dict(RiskMonitoring.QUARTER_CHOICES)[quarter],
        "quarter_choices": RiskMonitoring.QUARTER_CHOICES,
        "division_filter": division,
        "divisions": visible_divisions,
        "available_years": available_years,
        "division_rows": division_rows,
        "totals": totals,
        "priority_risks": priority_risks,
        "monitoring_count": len(monitorings),
    })


@risk_write_required
def monitoring_create(request, risk_pk):
    risk = get_object_or_404(risks_for_user(request.user), pk=risk_pk)
    if not can_edit_risk(request.user, risk):
        raise PermissionDenied("Anda tidak dapat mengubah pemantauan risiko divisi lain.")
    initial = {
        "year": _current_period()[0], "quarter": _current_period()[1],
        "initial_likelihood": risk.inherent_likelihood,
        "initial_impact": risk.inherent_impact,
        "final_likelihood": risk.residual_likelihood,
        "final_impact": risk.residual_impact,
    }
    form = RiskMonitoringForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        if RiskMonitoring.objects.filter(
            risk=risk, year=form.cleaned_data["year"], quarter=form.cleaned_data["quarter"],
        ).exists():
            form.add_error(None, "Pemantauan untuk risiko dan periode ini sudah ada.")
        else:
            monitoring = form.save(commit=False)
            monitoring.risk = risk
            monitoring.updated_by = request.user
            monitoring.save()
            RiskActivity.objects.create(
                risk=risk, actor=request.user, action="monitoring_created",
                description=f"Pemantauan {monitoring.get_quarter_display()} {monitoring.year} dibuat.",
            )
            messages.success(request, "Pemantauan triwulan berhasil ditambahkan.")
            return redirect("risk:risk_detail", pk=risk.pk)
    return render(request, "risk_management/monitoring_form.html", {
        "form": form, "risk": risk, "page_title": "Tambah Pemantauan Triwulan",
    })


@risk_write_required
def monitoring_edit(request, pk):
    monitoring = get_object_or_404(
        RiskMonitoring.objects.select_related("risk"), pk=pk,
        risk__in=risks_for_user(request.user),
    )
    if not can_edit_risk(request.user, monitoring.risk):
        raise PermissionDenied("Anda tidak dapat mengubah pemantauan risiko divisi lain.")
    form = RiskMonitoringForm(request.POST or None, instance=monitoring)
    if request.method == "POST" and form.is_valid():
        if RiskMonitoring.objects.filter(
            risk=monitoring.risk, year=form.cleaned_data["year"],
            quarter=form.cleaned_data["quarter"],
        ).exclude(pk=monitoring.pk).exists():
            form.add_error(None, "Pemantauan untuk risiko dan periode ini sudah ada.")
        else:
            monitoring = form.save(commit=False)
            monitoring.updated_by = request.user
            monitoring.save()
            RiskActivity.objects.create(
                risk=monitoring.risk, actor=request.user, action="monitoring_updated",
                description=f"Pemantauan {monitoring.get_quarter_display()} {monitoring.year} diperbarui.",
            )
            messages.success(request, "Pemantauan triwulan berhasil diperbarui.")
            return redirect("risk:risk_detail", pk=monitoring.risk_id)
    return render(request, "risk_management/monitoring_form.html", {
        "form": form, "risk": monitoring.risk, "monitoring": monitoring,
        "page_title": "Edit Pemantauan Triwulan",
    })


@risk_write_required
def action_create(request, monitoring_pk):
    monitoring = get_object_or_404(
        RiskMonitoring.objects.select_related("risk"), pk=monitoring_pk,
        risk__in=risks_for_user(request.user),
    )
    if not can_edit_risk(request.user, monitoring.risk):
        raise PermissionDenied("Anda tidak dapat mengubah rencana aksi divisi lain.")
    form = RiskActionPlanForm(request.POST or None, initial={
        "responsible_person": monitoring.risk.risk_owner,
    })
    if request.method == "POST" and form.is_valid():
        action = form.save(commit=False)
        action.monitoring = monitoring
        action.created_by = request.user
        action.updated_by = request.user
        action.save()
        RiskActivity.objects.create(
            risk=monitoring.risk, actor=request.user, action="action_created",
            description="Rencana aksi pemantauan ditambahkan.",
        )
        messages.success(request, "Rencana aksi berhasil ditambahkan.")
        return redirect("risk:risk_detail", pk=monitoring.risk_id)
    return render(request, "risk_management/action_form.html", {
        "form": form, "monitoring": monitoring, "page_title": "Tambah Rencana Aksi",
    })


@risk_write_required
def action_edit(request, pk):
    action = get_object_or_404(
        RiskActionPlan.objects.select_related("monitoring__risk"), pk=pk,
        monitoring__risk__in=risks_for_user(request.user),
    )
    risk = action.monitoring.risk
    if not can_edit_risk(request.user, risk):
        raise PermissionDenied("Anda tidak dapat mengubah rencana aksi divisi lain.")
    form = RiskActionPlanForm(request.POST or None, instance=action)
    if request.method == "POST" and form.is_valid():
        action = form.save(commit=False)
        action.updated_by = request.user
        action.save()
        RiskActivity.objects.create(
            risk=risk, actor=request.user, action="action_updated",
            description="Rencana aksi dan realisasi diperbarui.",
        )
        messages.success(request, "Rencana aksi berhasil diperbarui.")
        return redirect("risk:risk_detail", pk=risk.pk)
    return render(request, "risk_management/action_form.html", {
        "form": form, "monitoring": action.monitoring, "action": action,
        "page_title": "Edit Rencana Aksi dan Realisasi",
    })
