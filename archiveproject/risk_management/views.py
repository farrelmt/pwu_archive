from uuid import uuid4
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone

from accounts.activity_views import system_activity_log
from accounts.audit import record_activity

from .access import MANAGER_ROLES, can_edit_risk, can_manage_division_pic, risk_required, risk_write_required, risks_for_user
from .criteria import IMPACT_HEADERS, impact_criteria
from .forms import (
    AdditionalCauseFormSet,
    AdditionalControlFormSet,
    AdditionalRiskFormSet,
    AnnualRiskReportForm,
    DivisionPICForm,
    RiskTreatmentForm,
    RiskTreatmentFormSet,
    RiskActionPlanForm,
    RiskMonitoringForm,
    RiskMonitoringExcelForm,
    MonitoringExcelActionFormSet,
    RiskRegisterForm,
    RiskWorkbookImportForm,
    pic_name,
)
from .models import (
    RiskActionPlan,
    RiskAccess,
    RiskActivity,
    RiskCause,
    RiskControl,
    RiskDivision,
    RiskMonitoring,
    RiskRegister,
    RiskTreatment,
)
from .scoring import MATRIX_COLORS, LEVEL_BY_COLOR, LEVEL_ORDER, level_filter, level_rank
from .services import import_risk_workbook
from .exports import annual_risk_workbook, empty_import_workbook


def _log(request, action, description, target=None, *, target_label=None, metadata=None, success=True):
    details = {
        "path": request.path,
        "method": request.method,
        "actor_name": request.user.get_full_name() or request.user.get_username(),
    }
    details.update(metadata or {})
    record_activity(
        category="RISK",
        action=action,
        description=description,
        request=request,
        target_type=target.__class__.__name__ if target is not None else "RiskManagement",
        target_id=target.pk if target is not None else "",
        target_label=(target_label or (str(target) if target is not None else "Manajemen Risiko"))[:255],
        metadata=details,
        success=success,
    )


def activity_log(request):
    return system_activity_log(
        request,
        category="RISK",
        system_name="Sistem Manajemen Risiko",
        base_template="risk_management/base.html",
        activity_url_name="risk:activity_log",
    )


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
    risks = risks_for_user(request.user)
    today = timezone.localdate()
    summary = risks.aggregate(
        total=Count("pk", distinct=True),
        open=Count("pk", filter=~Q(status="closed"), distinct=True),
        overdue=Count(
            "pk",
            filter=Q(target_date__lt=today) & ~Q(status="closed"),
            distinct=True,
        ),
        divisions=Count("division_id", distinct=True),
        very_low=Count("pk", filter=level_filter("Sangat Rendah", "residual_likelihood", "residual_impact"), distinct=True),
        low=Count("pk", filter=level_filter("Rendah", "residual_likelihood", "residual_impact"), distinct=True),
        medium=Count("pk", filter=level_filter("Sedang", "residual_likelihood", "residual_impact"), distinct=True),
        high=Count("pk", filter=level_filter("Tinggi", "residual_likelihood", "residual_impact"), distinct=True),
        very_high=Count("pk", filter=level_filter("Sangat Tinggi", "residual_likelihood", "residual_impact"), distinct=True),
    )
    counts = {
        "Sangat_Rendah": summary["very_low"],
        "Rendah": summary["low"],
        "Sedang": summary["medium"],
        "Tinggi": summary["high"],
        "Sangat_Tinggi": summary["very_high"],
    }
    year, quarter = _current_period()
    current_monitorings = list(
        RiskMonitoring.objects.filter(
            risk__in=risks_for_user(request.user), year=year, quarter=quarter,
        ).select_related("risk__division").prefetch_related("action_plans")
    )
    division_rows, monitoring_totals = _monitoring_summary(current_monitorings)
    response = render(request, "risk_management/dashboard.html", {
        "total_risks": summary["total"],
        "open_risks": summary["open"],
        "overdue_risks": summary["overdue"],
        "level_counts": counts,
        "recent_risks": risks[:8],
        "division_count": summary["divisions"],
        "monitoring_year": year,
        "monitoring_quarter": quarter,
        "monitoring_quarter_label": dict(RiskMonitoring.QUARTER_CHOICES)[quarter],
        "monitoring_totals": monitoring_totals,
        "division_rows": division_rows,
    })
    _log(request, "RISK_DASHBOARD_VIEWED", "Membuka ringkasan Manajemen Risiko.")
    return response


@risk_required
def risk_list(request):
    risks = risks_for_user(request.user)
    sort_fields = {
        "code": "risk_code", "title": "title", "division": "division__name",
        "category": "code_category", "inherent": "sort_inherent",
        "residual": "sort_residual", "status": "status",
    }
    sort_key = request.GET.get("sort", "")
    direction = "desc" if request.GET.get("order") == "desc" else "asc"
    if sort_key in sort_fields:
        risks = risks.annotate(
            sort_inherent=level_rank("inherent_likelihood", "inherent_impact"),
            sort_residual=level_rank("residual_likelihood", "residual_impact"),
        ).order_by(("-" if direction == "desc" else "") + sort_fields[sort_key], "pk")
    else:
        sort_key = ""
    available_years = [item.year for item in risks.dates("created_at", "year", order="DESC")]
    year = request.GET.get("year", "").strip()
    if not (year.isascii() and year.isdigit() and len(year) == 4 and 1 <= int(year) <= 9999):
        year = ""
    if year:
        risks = risks.filter(created_at__year=int(year))
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
    if category in dict(RiskRegister.CODE_CATEGORY_CHOICES):
        risks = risks.filter(code_category=category)
    if level:
        level_name = next((name for name in LEVEL_BY_COLOR.values() if name.lower() == level.lower()), None)
        if level_name is None:
            risks = risks.none()
        else:
            risks = risks.filter(level_filter(level_name, "residual_likelihood", "residual_impact"))
    register_summary = risks.aggregate(
        total=Count("pk"), priority=Count("pk", filter=Q(is_priority=True)),
        high=Count("pk", filter=level_filter("Tinggi", "residual_likelihood", "residual_impact") |
                   level_filter("Sangat Tinggi", "residual_likelihood", "residual_impact")),
        closed=Count("pk", filter=Q(status="closed")),
    )
    page_obj = Paginator(risks, 20).get_page(request.GET.get("page"))
    visible_divisions = RiskDivision.objects.filter(risks__in=risks_for_user(request.user)).distinct()
    active_filters = []
    if search:
        active_filters.append({"key": "q", "label": "Pencarian", "value": search})
    if year:
        active_filters.append({"key": "year", "label": "Tahun", "value": year})
    if division:
        division_label = next((item.name for item in visible_divisions if str(item.pk) == division), division)
        active_filters.append({"key": "division", "label": "Divisi", "value": division_label})
    for key, value, label, choices in (
        ("status", status, "Status", dict(RiskRegister.STATUS_CHOICES)),
        ("category", category, "Kategori", dict(RiskRegister.CODE_CATEGORY_CHOICES)),
        ("level", level, "Level", {}),
    ):
        if value:
            active_filters.append({"key": key, "label": label, "value": choices.get(value, value.title())})
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    response = render(request, "risk_management/risk_list.html", {
        "page_obj": page_obj, "divisions": visible_divisions,
        "register_summary": register_summary, "active_filters": active_filters,
        "available_years": available_years,
        "sorting_enabled": True, "sort_key": sort_key, "sort_order": direction,
        "pagination_query": pagination_params.urlencode(),
        "statuses": RiskRegister.STATUS_CHOICES, "categories": RiskRegister.CODE_CATEGORY_CHOICES,
        "filters": {"q": search, "division": division, "status": status, "category": category, "level": level, "year": year},
    })
    _log(
        request, "RISK_REGISTER_VIEWED", "Membuka Register Risiko.",
        metadata={
            "year": year, "division": division, "search": search[:255],
            "status": status, "category": category, "level": level,
            "sort": sort_key, "order": direction, "page": page_obj.number,
            "result_count": page_obj.paginator.count,
        },
    )
    return response


@risk_write_required
@require_GET
def workbook_import_template(request):
    return FileResponse(
        empty_import_workbook(),
        as_attachment=True,
        filename=f"Template Impor Manajemen Risiko {timezone.localdate().year}.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@risk_write_required
def workbook_import(request):
    form = RiskWorkbookImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        access_rows = request.risk_accesses
        is_manager = request.user.is_superuser or any(
            access.role in MANAGER_ROLES for access in access_rows
        )
        allowed_division_ids = None
        if not is_manager:
            allowed_division_ids = {
                access.division_id
                for access in access_rows
                if access.role == "risk_officer" and access.division_id is not None
            }
        try:
            stats = import_risk_workbook(
                form.cleaned_data["workbook"],
                user=request.user,
                allowed_division_ids=allowed_division_ids,
            )
        except ValidationError as exc:
            form.add_error("workbook", exc)
        else:
            _log(
                request, "RISK_WORKBOOK_IMPORTED", f"Mengimpor workbook risiko untuk {stats['division']}.",
                target_label=form.cleaned_data["workbook"].name,
                metadata={"filename": form.cleaned_data["workbook"].name, **stats},
            )
            messages.success(
                request,
                "Workbook berhasil diimpor untuk %(division)s: %(risks_created)s risiko baru, "
                "%(risks_updated)s diperbarui, %(treatments_created)s perlakuan, "
                "%(monitorings_created)s pemantauan, dan %(actions_created)s rencana aksi baru."
                % stats,
            )
            return redirect("risk:risk_list")
    if request.method == "POST":
        upload = request.FILES.get("workbook")
        _log(
            request, "RISK_WORKBOOK_IMPORT_FAILED", "Impor workbook risiko gagal divalidasi.",
            target_label=getattr(upload, "name", "Workbook risiko"),
            metadata={"filename": getattr(upload, "name", ""), "error_fields": list(form.errors)},
            success=False,
        )
    return render(request, "risk_management/workbook_import.html", {"form": form})


@risk_required
def annual_report(request):
    visible_risks = risks_for_user(request.user)
    divisions = RiskDivision.objects.filter(risks__in=visible_risks).distinct().order_by("name")
    initial = {"year": timezone.localdate().year}
    if divisions.count() == 1:
        initial["division"] = divisions.first().pk
    if request.GET.get("year", "").isdigit():
        initial["year"] = request.GET["year"]
    if request.GET.get("division", "").isdigit():
        initial["division"] = request.GET["division"]
    form = AnnualRiskReportForm(
        request.GET if request.GET.get("download") == "1" else None,
        divisions=divisions, initial=initial,
    )
    if form.is_bound and form.is_valid():
        year = form.cleaned_data["year"]
        division = form.cleaned_data["division"]
        risks = visible_risks.filter(
            Q(created_at__year=year) | Q(monitorings__year=year)
        )
        if division is not None:
            risks = risks.filter(division=division)
        risks = risks.distinct().order_by("risk_code").prefetch_related(
            "treatments", "additional_causes", "additional_controls",
            Prefetch("monitorings", queryset=RiskMonitoring.objects.filter(
                year=year,
            ).prefetch_related("action_plans")),
        )
        if not risks.exists():
            form.add_error(None, "Tidak ada data risiko untuk tahun dan divisi yang dipilih.")
        else:
            division_name = division.name if division else "Semua Divisi"
            download_mark = {
                "version": 1,
                "download_id": str(uuid4()),
                "user_id": str(request.user.pk),
                "username": request.user.get_username(),
                "full_name": request.user.get_full_name() or request.user.get_username(),
                "downloaded_at": timezone.now().astimezone(ZoneInfo("Asia/Jakarta")).isoformat(),
                "year": year,
                "division_id": division.pk if division else None,
            }
            try:
                workbook = annual_risk_workbook(risks, division=division, year=year, download_mark=download_mark)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                from django.utils.text import slugify
                filename = f"Manajemen Risiko {year} - {slugify(division_name)}.xlsx"
                response = FileResponse(
                    workbook, as_attachment=True, filename=filename,
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                response["Cache-Control"] = "private, no-store"
                _log(
                    request, "ANNUAL_REPORT_DOWNLOADED",
                    f"Menyiapkan unduhan laporan tahunan {year} untuk {division_name}: {filename}.",
                    division, target_label=filename,
                    metadata={
                        "year": year, "division_id": division.pk if division else None,
                        "division": division_name,
                        "filename": filename, "risk_count": len(risks), "format": "xlsx",
                        "delivery": "response_prepared",
                        "download_mark": download_mark,
                    },
                )
                return response
    if form.is_bound:
        _log(
            request, "ANNUAL_REPORT_DOWNLOAD_FAILED", "Permintaan unduhan laporan tahunan tidak dapat dipenuhi.",
            metadata={
                "year": request.GET.get("year", "")[:32],
                "division_id": request.GET.get("division", "")[:32],
                "error_fields": list(form.errors),
            }, success=False,
        )
    return render(request, "risk_management/annual_report.html", {"form": form})


@risk_required
def scoring_guide(request):
    likelihoods = [
        (5, "Hampir Pasti", "≥ 90%", "Akan sering terjadi."),
        (4, "Kemungkinan Besar", "50% ≤ x < 90%", "Dapat terjadi dengan mudah."),
        (3, "Mungkin", "30% ≤ x < 50%", "Dapat terjadi walau tidak sering."),
        (2, "Kemungkinan Kecil", "10% ≤ x < 30%", "Dapat muncul pada suatu waktu."),
        (1, "Hampir Mustahil", "0,01% ≤ x < 10%", "Terjadi hanya dalam keadaan ekstrem."),
    ]
    risk_levels = [
        ("Sangat Tinggi", "Merah", "red"), ("Tinggi", "Coklat", "orange"),
        ("Sedang", "Kuning", "yellow"), ("Rendah", "Hijau", "green"),
        ("Sangat Rendah", "Biru", "blue"),
    ]
    matrix = [
        {"impact": impact, "cells": [
            {"level": RiskRegister.level_for(likelihood, impact),
             "likelihood": likelihood, "color": MATRIX_COLORS[impact - 1][likelihood - 1]}
            for likelihood in range(1, 6)
        ]}
        for impact in range(5, 0, -1)
    ]
    return render(request, "risk_management/scoring_guide.html", {
        "likelihoods": likelihoods,
        "risk_levels": risk_levels,
        "matrix": matrix,
        "impact_headers": IMPACT_HEADERS,
        "impact_criteria": impact_criteria(),
    })


@risk_required
def risk_detail(request, pk):
    risk = get_object_or_404(
        risks_for_user(request.user).prefetch_related(
            "treatments",
            Prefetch(
                "monitorings",
                queryset=RiskMonitoring.objects.prefetch_related("action_plans").select_related("updated_by"),
            )
        ),
        pk=pk,
    )
    can_edit_this = can_edit_risk(request.user, risk)
    year_value = request.POST.get("monitoring_year") if request.method == "POST" else request.GET.get("monitoring_year")
    if year_value and year_value.isdigit() and 2020 <= int(year_value) <= 2100:
        selected_year = int(year_value)
    elif request.method == "POST":
        return HttpResponseBadRequest("Tahun pemantauan tidak valid.")
    else:
        selected_year = _current_period()[0]
    quarter_value = request.POST.get("save_quarter") if request.method == "POST" else request.GET.get("monitoring_quarter")
    selected_quarter = int(quarter_value) if quarter_value and quarter_value.isdigit() and int(quarter_value) in range(1, 5) else 1
    existing_monitorings = list(risk.monitorings.all())
    treatments = list(risk.treatments.all())
    by_quarter = {item.quarter: item for item in existing_monitorings if item.year == selected_year}
    selected_form = None
    selected_actions = None
    submitted_quarter = None
    if request.method == "POST":
        if not can_edit_this:
            raise PermissionDenied("Anda tidak dapat mengubah pemantauan risiko divisi lain.")
        quarter_value = request.POST.get("save_quarter", "")
        if not quarter_value.isdigit() or int(quarter_value) not in range(1, 5):
            return HttpResponseBadRequest("Triwulan pemantauan tidak valid.")
        submitted_quarter = int(quarter_value)
        data = request.POST.copy()
        data[f"q{submitted_quarter}-year"] = selected_year
        data[f"q{submitted_quarter}-quarter"] = submitted_quarter
        existing = by_quarter.get(submitted_quarter)
        selected_form = RiskMonitoringExcelForm(data, instance=existing, prefix=f"q{submitted_quarter}")
        selected_form.instance.risk = risk
        selected_actions = MonitoringExcelActionFormSet(
            request.POST, instance=selected_form.instance, prefix=f"q{submitted_quarter}-actions",
            form_kwargs={"risk": risk},
        )
        monitoring_valid = selected_form.is_valid()
        actions_valid = selected_actions.is_valid()
        if monitoring_valid and actions_valid:
            with transaction.atomic():
                monitoring = selected_form.save(commit=False)
                monitoring.risk = risk
                monitoring.updated_by = request.user
                monitoring.save()
                selected_actions.instance = monitoring
                actions = selected_actions.save(commit=False)
                for action in selected_actions.deleted_objects:
                    action.delete()
                for action in actions:
                    if action.pk is None:
                        action.created_by = request.user
                    if action.treatment_id:
                        action.description = action.treatment.action_plan
                    action.updated_by = request.user
                    action.save()
            action = "monitoring_updated" if existing else "monitoring_created"
            RiskActivity.objects.create(
                risk=risk, actor=request.user, action=action,
                description=f"Pemantauan {monitoring.get_quarter_display()} {selected_year} {'diperbarui' if existing else 'dibuat'}.",
            )
            _log(
                request, "MONITORING_UPDATED" if existing else "MONITORING_CREATED",
                f"{'Memperbarui' if existing else 'Menambahkan'} pemantauan {monitoring.get_quarter_display()} {selected_year}.",
                monitoring, target_label=risk.risk_code,
            )
            messages.success(request, f"Pemantauan {monitoring.get_quarter_display()} {selected_year} berhasil disimpan.")
            return redirect(f"{reverse('risk:risk_detail', args=[risk.pk])}?monitoring_year={selected_year}&monitoring_quarter={submitted_quarter}#pemantauan-triwulan")

    monitoring_rows = []
    for quarter, label in RiskMonitoring.QUARTER_CHOICES:
        if quarter != selected_quarter:
            continue
        existing = by_quarter.get(quarter)
        initial = {
            "year": selected_year, "quarter": quarter,
            "initial_likelihood": risk.inherent_likelihood,
            "initial_impact": risk.inherent_impact,
            "final_likelihood": risk.residual_likelihood,
            "final_impact": risk.residual_impact,
        }
        form = selected_form if submitted_quarter == quarter else RiskMonitoringExcelForm(
            instance=existing, initial=initial, prefix=f"q{quarter}",
        )
        linked_treatments = {
            action.treatment_id for action in existing.action_plans.all()
        } if existing else set()
        initial_actions = [
            {
                "treatment": treatment.pk,
                "description": treatment.action_plan,
                "target_date": treatment.target_date,
                "responsible_person": treatment.responsible_person or risk.risk_owner,
            }
            for treatment in treatments if treatment.pk not in linked_treatments
        ]
        if not initial_actions and not (existing and existing.action_plans.all()):
            initial_actions = [{}]
        action_formset = selected_actions if submitted_quarter == quarter else MonitoringExcelActionFormSet(
            instance=existing or RiskMonitoring(risk=risk, year=selected_year, quarter=quarter),
            prefix=f"q{quarter}-actions", initial=initial_actions,
            form_kwargs={"risk": risk},
        )
        if submitted_quarter != quarter:
            action_formset.extra = len(initial_actions)
        monitoring_rows.append({
            "quarter": quarter, "label": label, "monitoring": existing,
            "form": form, "action_formset": action_formset,
            "table_items": [existing] if existing else [],
        })
    response = render(request, "risk_management/risk_detail.html", {
        "risk": risk, "can_edit_this": can_edit_this,
        "monitoring_rows": monitoring_rows,
        "monitoring_year": selected_year,
        "monitoring_quarter": selected_quarter,
        "previous_quarter": selected_quarter - 1 if selected_quarter > 1 else None,
        "next_quarter": selected_quarter + 1 if selected_quarter < 4 else None,
        "monitoring_years": sorted({selected_year, _current_period()[0], *(item.year for item in existing_monitorings)}, reverse=True),
        "treatment_risks": [risk],
    })
    if request.method == "GET":
        _log(request, "RISK_VIEWED", f"Membuka detail risiko {risk.risk_code}.", risk, target_label=risk.risk_code)
    return response


@risk_required
def treatment_list(request):
    risks = risks_for_user(request.user).order_by("risk_code").prefetch_related("treatments")
    page_obj = Paginator(risks, 20).get_page(request.GET.get("page"))
    for risk in page_obj:
        risk.can_edit_treatment = can_edit_risk(request.user, risk)
    return render(request, "risk_management/treatment_list.html", {
        "page_obj": page_obj, "treatment_risks": page_obj,
    })


@risk_write_required
def treatment_create(request):
    form = RiskTreatmentForm(request.POST if request.method == "POST" else None,
                             user=request.user, initial={"risk": request.GET.get("risk")})
    if request.method == "POST" and form.is_valid():
        treatment = form.save(commit=False)
        treatment.created_by = treatment.updated_by = request.user
        with transaction.atomic():
            treatment.save()
            RiskActivity.objects.create(risk=treatment.risk, actor=request.user, action="treatment_created",
                                        description="Perlakuan risiko ditambahkan.")
            _log(request, "RISK_TREATMENT_CREATED", "Menambahkan perlakuan risiko.", treatment,
                 target_label=treatment.risk.risk_code)
        messages.success(request, "Perlakuan risiko berhasil ditambahkan.")
        return redirect("risk:risk_detail", pk=treatment.risk_id)
    return render(request, "risk_management/treatment_form.html", {
        "form": form, "page_title": "Tambah Perlakuan Risiko",
        "risk_level_matrix": [[LEVEL_BY_COLOR[color] for color in row] for row in MATRIX_COLORS],
    })


@risk_write_required
def treatment_edit(request, pk):
    treatment = get_object_or_404(RiskTreatment.objects.select_related("risk"), pk=pk,
                                  risk__in=risks_for_user(request.user))
    if not can_edit_risk(request.user, treatment.risk):
        raise PermissionDenied("Anda tidak dapat mengubah perlakuan risiko divisi lain.")
    form = RiskTreatmentForm(request.POST if request.method == "POST" else None,
                             user=request.user, instance=treatment)
    if request.method == "POST" and form.is_valid():
        treatment = form.save(commit=False)
        treatment.updated_by = request.user
        with transaction.atomic():
            treatment.save()
            RiskActivity.objects.create(risk=treatment.risk, actor=request.user, action="treatment_updated",
                                        description="Perlakuan risiko diperbarui.")
            _log(request, "RISK_TREATMENT_UPDATED", "Memperbarui perlakuan risiko.", treatment,
                 target_label=treatment.risk.risk_code,
                 metadata={"changed_fields": [form.fields[name].label for name in form.changed_data]})
        messages.success(request, "Perlakuan risiko berhasil diperbarui.")
        return redirect("risk:risk_detail", pk=treatment.risk_id)
    return render(request, "risk_management/treatment_form.html", {
        "form": form, "treatment": treatment, "page_title": "Edit Perlakuan Risiko",
        "risk_level_matrix": [[LEVEL_BY_COLOR[color] for color in row] for row in MATRIX_COLORS],
    })


@risk_write_required
def risk_create(request):
    identification_only = request.method == "POST" and request.POST.get("save_scope") == "identification"
    form = RiskRegisterForm(request.POST or None, user=request.user, identification_only=identification_only)
    additional = AdditionalRiskFormSet(
        request.POST if request.method == "POST" and "additional-TOTAL_FORMS" in request.POST else None,
        prefix="additional", form_kwargs={"user": request.user, "identification_only": identification_only},
    )
    treatments = _risk_treatment_formset(request, form.instance, bind=not identification_only)
    causes = _risk_cause_formset(request)
    controls = _risk_control_formset(request, bind=not identification_only)
    form_valid = form.is_valid() if request.method == "POST" else False
    additional_valid = additional.is_valid() if additional.is_bound else True
    treatments_valid = treatments.is_valid() if treatments.is_bound else True
    causes_valid = causes.is_valid() if causes.is_bound else True
    controls_valid = controls.is_valid() if controls.is_bound else True
    def active_additional(index):
        return index <= len(additional.forms) and (
            index == 0 or (additional.forms[index - 1].has_changed()
                           and not additional.forms[index - 1].cleaned_data.get("DELETE"))
        )
    if causes_valid and causes.is_bound:
        for cause_form in causes.forms:
            if cause_form.cleaned_data.get("DELETE"):
                continue
            index = cause_form.cleaned_data.get("risk_index")
            if index is None or not active_additional(index):
                cause_form.add_error("risk_index", "Pilih baris risiko yang sudah diisi.")
                causes_valid = False
    if controls_valid and controls.is_bound:
        for control_form in controls.forms:
            if control_form.cleaned_data.get("DELETE") or not control_form.cleaned_data:
                continue
            index = control_form.cleaned_data.get("risk_index")
            if index is None or not active_additional(index):
                control_form.add_error("risk_index", "Pilih baris risiko yang sudah diisi.")
                controls_valid = False
    if request.method == "POST" and form_valid and additional_valid and treatments_valid and causes_valid and controls_valid:
        for treatment_form in treatments.forms if treatments.is_bound else []:
            if (not treatment_form.has_changed() or treatment_form.cleaned_data.get("DELETE")
                    or not treatment_form.cleaned_data.get("action_plan")):
                continue
            index = treatment_form.cleaned_data.get("risk_index") or 0
            if not active_additional(index):
                treatment_form.add_error("risk_index", "Pilih risiko yang sudah diisi pada Identifikasi Risiko.")
                treatments_valid = False
        # The row index follows the identification rows, including any blank rows.
    if request.method == "POST" and form_valid and additional_valid and treatments_valid and causes_valid and controls_valid:
        with transaction.atomic():
            risk = form.save(commit=False)
            risk.created_by = request.user
            risk.updated_by = request.user
            risk.save()
            risks_by_index = {0: risk}
            RiskActivity.objects.create(risk=risk, actor=request.user, action="created", description="Risiko dibuat.")
            _log(request, "RISK_CREATED", "Menambahkan risiko baru.", risk, target_label=risk.risk_code)
            for index, item in enumerate(additional.forms, 1):
                if not item.has_changed() or item.cleaned_data.get("DELETE"):
                    continue
                added = item.save(commit=False)
                added.created_by = added.updated_by = request.user
                added.save()
                risks_by_index[index] = added
                RiskActivity.objects.create(risk=added, actor=request.user, action="created", description="Risiko dibuat.")
                _log(request, "RISK_CREATED", "Menambahkan risiko baru.", added, target_label=added.risk_code)
            _save_risk_causes(causes, risks_by_index)
            _save_risk_controls(controls, risks_by_index)
            if treatments.is_bound:
                for row in treatments.forms:
                    if not row.has_changed() or row.cleaned_data.get("DELETE"):
                        continue
                    item = row.save(commit=False)
                    index = row.cleaned_data.get("risk_index") or 0
                    item.risk = risks_by_index[index]
                    item.created_by = item.updated_by = request.user
                    item.save()
                    _log(request, "RISK_TREATMENT_CREATED", "Menyimpan perlakuan pada formulir risiko.", item,
                         target_label=item.risk.risk_code)
                    RiskActivity.objects.create(risk=item.risk, actor=request.user,
                                                action="treatment_created", description="Perlakuan risiko disimpan.")
        if identification_only:
            messages.success(request, f"Identifikasi {len(risks_by_index)} risiko tersimpan. Analisis dan perlakuan dapat dilengkapi nanti.")
        else:
            messages.success(request, f"{len(risks_by_index)} risiko berhasil ditambahkan.")
        return redirect("risk:risk_detail", pk=risk.pk) if len(risks_by_index) == 1 else redirect("risk:risk_list")
    return render(request, "risk_management/risk_form.html", {
        "form": form, "additional_formset": additional, "cause_formset": causes,
        "control_formset": controls,
        "treatment_formset": treatments, "page_title": "Tambah Risiko",
        "risk_level_matrix": [[LEVEL_BY_COLOR[color] for color in row] for row in MATRIX_COLORS],
    })


@risk_write_required
def risk_edit(request, pk):
    risk = get_object_or_404(risks_for_user(request.user), pk=pk)
    if not can_edit_risk(request.user, risk):
        raise PermissionDenied("Anda tidak dapat mengubah risiko divisi lain.")
    identification_only = request.method == "POST" and request.POST.get("save_scope") == "identification"
    form = RiskRegisterForm(request.POST or None, instance=risk, user=request.user,
                            identification_only=identification_only)
    treatments = _risk_treatment_formset(request, risk, bind=not identification_only)
    causes = _risk_cause_formset(request, risk)
    controls = _risk_control_formset(request, risk, bind=not identification_only)
    causes_valid = causes.is_valid() if causes.is_bound else True
    if causes_valid and causes.is_bound:
        for cause_form in causes.forms:
            if not cause_form.cleaned_data.get("DELETE") and cause_form.cleaned_data.get("risk_index") != 0:
                cause_form.add_error("risk_index", "Baris risiko tidak valid.")
                causes_valid = False
    controls_valid = controls.is_valid() if controls.is_bound else True
    if controls_valid and controls.is_bound:
        for control_form in controls.forms:
            if (not control_form.cleaned_data.get("DELETE") and control_form.cleaned_data
                    and control_form.cleaned_data.get("risk_index") != 0):
                control_form.add_error("risk_index", "Baris risiko tidak valid.")
                controls_valid = False
    if request.method == "POST" and all([form.is_valid(), not treatments.is_bound or treatments.is_valid(), causes_valid, controls_valid]):
        with transaction.atomic():
            risk = form.save(commit=False)
            risk.updated_by = request.user
            risk.save()
            if causes.is_bound:
                risk.additional_causes.all().delete()
                _save_risk_causes(causes, {0: risk})
            if controls.is_bound:
                risk.additional_controls.all().delete()
                _save_risk_controls(controls, {0: risk})
            _save_risk_treatments(request, risk, treatments)
            RiskActivity.objects.create(risk=risk, actor=request.user, action="updated", description="Data risiko diperbarui.")
            _log(
                request, "RISK_UPDATED", "Memperbarui data risiko.", risk, target_label=risk.risk_code,
                metadata={"changed_fields": [form.fields[name].label for name in form.changed_data]},
            )
        if identification_only:
            messages.success(request, f"Identifikasi {risk.risk_code} tersimpan. Analisis dan perlakuan dapat dilengkapi nanti.")
        else:
            messages.success(request, f"{risk.risk_code} berhasil diperbarui.")
        return redirect("risk:risk_detail", pk=risk.pk)
    return render(request, "risk_management/risk_form.html", {
        "form": form, "risk": risk, "cause_formset": causes,
        "control_formset": controls,
        "treatment_formset": treatments, "page_title": "Edit Risiko",
        "risk_level_matrix": [[LEVEL_BY_COLOR[color] for color in row] for row in MATRIX_COLORS],
    })


@risk_write_required
@require_POST
def risk_delete(request, pk):
    risk = get_object_or_404(risks_for_user(request.user), pk=pk)
    if not can_edit_risk(request.user, risk):
        raise PermissionDenied("Anda tidak dapat menghapus risiko divisi lain.")
    with transaction.atomic():
        _log(request, "RISK_DELETED", "Menghapus risiko.", risk, target_label=risk.risk_code)
        risk.delete()
    messages.success(request, "Risiko berhasil dihapus.")
    return redirect("risk:risk_list")


def _risk_cause_formset(request, risk=None):
    data = request.POST if request.method == "POST" and "causes-TOTAL_FORMS" in request.POST else None
    initial = [
        {
            "risk_index": 0, "description": cause.description,
            "controllability": cause.controllability, "impact": cause.impact,
            "inherent_likelihood": cause.inherent_likelihood,
            "inherent_impact": cause.inherent_impact,
            "identification_notes": cause.identification_notes,
        }
        for cause in risk.additional_causes.all()
    ] if risk else []
    return AdditionalCauseFormSet(data, initial=initial, prefix="causes")


def _save_risk_causes(formset, risks_by_index):
    if not formset.is_bound:
        return
    positions = {index: 1 for index in risks_by_index}
    for cause_form in formset.forms:
        data = cause_form.cleaned_data
        if data.get("DELETE"):
            continue
        index = data["risk_index"]
        positions[index] += 1
        RiskCause.objects.create(
            risk=risks_by_index[index], position=positions[index],
            description=data["description"], controllability=data["controllability"],
            impact=data["impact"], inherent_likelihood=data["inherent_likelihood"],
            inherent_impact=data["inherent_impact"],
            identification_notes=data["identification_notes"],
        )


def _risk_control_formset(request, risk=None, *, bind=True):
    data = request.POST if bind and request.method == "POST" and "controls-TOTAL_FORMS" in request.POST else None
    initial = [
        {
            "risk_index": 0, "description": control.description,
            "effectiveness": control.effectiveness, "notes": control.notes,
        }
        for control in risk.additional_controls.all()
    ] if risk else []
    return AdditionalControlFormSet(data, initial=initial, prefix="controls")


def _save_risk_controls(formset, risks_by_index):
    if not formset.is_bound:
        return
    positions = {index: 1 for index in risks_by_index}
    for control_form in formset.forms:
        data = control_form.cleaned_data
        if not data or data.get("DELETE"):
            continue
        index = data["risk_index"]
        positions[index] += 1
        RiskControl.objects.create(
            risk=risks_by_index[index], position=positions[index],
            description=data["description"], effectiveness=data["effectiveness"],
            notes=data["notes"],
        )


def _risk_treatment_formset(request, risk, *, bind=True):
    data = request.POST if bind and request.method == "POST" and any(
        key.startswith("treatments-") for key in request.POST
    ) else None
    formset = RiskTreatmentFormSet(data, instance=risk, prefix="treatments")
    if risk.pk and not formset.is_bound and risk.treatments.exists():
        formset.extra = 0
    return formset


def _save_risk_treatments(request, risk, formset):
    if not formset.is_bound:
        return
    formset.instance = risk
    treatments = formset.save(commit=False)
    for deleted in formset.deleted_objects:
        _log(request, "RISK_TREATMENT_DELETED", "Menghapus perlakuan pada formulir risiko.", deleted,
             target_label=risk.risk_code)
        RiskActivity.objects.create(risk=risk, actor=request.user, action="treatment_deleted",
                                    description="Perlakuan risiko dihapus.")
        deleted.delete()
    for treatment in treatments:
        created = not treatment.pk
        if created:
            treatment.created_by = request.user
        treatment.updated_by = request.user
        treatment.save()
        action = "CREATED" if created else "UPDATED"
        _log(request, f"RISK_TREATMENT_{action}", "Menyimpan perlakuan pada formulir risiko.", treatment,
             target_label=risk.risk_code)
        RiskActivity.objects.create(risk=risk, actor=request.user,
                                    action=f"treatment_{action.lower()}", description="Perlakuan risiko disimpan.")


@risk_required
def divisions(request):
    access_rows = RiskDivision.objects.filter(is_active=True).prefetch_related(Prefetch(
        "accesses", queryset=RiskAccess.objects.filter(is_active=True, user__is_active=True).select_related("user"),
    ))
    if not request.user.is_superuser and not any(
        access.role in MANAGER_ROLES for access in request.risk_accesses
    ):
        division_ids = {
            access.division_id for access in request.risk_accesses
            if access.division_id is not None
        }
        access_rows = access_rows.filter(pk__in=division_ids)
    access_rows = list(access_rows)
    for division in access_rows:
        people = {role: None for role in ("risk_officer", "division_head", "staff_it", "staff_hrd", "staff_humas")}
        for access in division.accesses.all():
            if access.role in people and people[access.role] is None:
                people[access.role] = access.user
        division.risk_officer_name = pic_name(people["risk_officer"]) if people["risk_officer"] else None
        division.risk_owner_name = pic_name(people["division_head"]) if people["division_head"] else None
        for role in ("staff_it", "staff_hrd", "staff_humas"):
            setattr(division, f"{role}_name", pic_name(people[role]) if people[role] else None)
        division.can_manage_pic = can_manage_division_pic(request.user, division)
    return render(request, "risk_management/divisions.html", {
        "divisions": access_rows, "can_manage_pic": can_manage_division_pic(request.user),
    })


@risk_required
def division_pic_edit(request, pk):
    division = get_object_or_404(RiskDivision, pk=pk, is_active=True)
    if not can_manage_division_pic(request.user, division):
        raise PermissionDenied("Anda tidak dapat mengubah PIC divisi ini.")
    form = DivisionPICForm(request.POST if request.method == "POST" else None, division=division)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            division = RiskDivision.objects.select_for_update().get(pk=division.pk)
            before, after = {}, {}
            assignments = [("risk_officer", "risk_officer"), ("risk_owner", "division_head")]
            if division.code == "LUM":
                assignments += [("staff_it", "staff_it"), ("staff_hrd", "staff_hrd"),
                                ("staff_humas", "staff_humas")]
            for name, role in assignments:
                rows = RiskAccess.objects.filter(division=division, role=role)
                before[role] = sorted(rows.filter(is_active=True).values_list("user_id", flat=True))
                user = form.cleaned_data[name]
                after[role] = [user.pk] if user else []
                rows.exclude(user_id=user.pk if user else None).filter(is_active=True).update(is_active=False)
                if user:
                    RiskAccess.objects.update_or_create(
                        division=division, role=role, user=user, defaults={"is_active": True},
                    )
            RiskRegister.objects.filter(division=division).update(
                risk_owner=pic_name(form.cleaned_data["risk_owner"]),
                risk_officer=pic_name(form.cleaned_data["risk_officer"]),
            )
            if before != after:
                _log(request, "DIVISION_PIC_UPDATED", f"Memperbarui PIC divisi {division.name}.", division,
                     metadata={"before": before, "after": after})
        messages.success(request, "PIC divisi berhasil diperbarui.")
        return redirect("risk:divisions")
    return render(request, "risk_management/division_pic_form.html", {"form": form, "division": division})


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
    sort_fields = {
        "title": lambda m: m.risk.title.casefold(),
        "initial_likelihood": lambda m: m.initial_likelihood,
        "initial_impact": lambda m: m.initial_impact,
        "initial_score": lambda m: LEVEL_ORDER.index(m.initial_level),
        "final_likelihood": lambda m: m.final_likelihood,
        "final_impact": lambda m: m.final_impact,
        "final_score": lambda m: LEVEL_ORDER.index(m.final_level),
        "expected_likelihood": lambda m: m.expected_likelihood,
        "expected_impact": lambda m: m.expected_impact,
        "expected_score": lambda m: LEVEL_ORDER.index(m.expected_level) if m.expected_level else None,
        "deviation": lambda m: m.deviation,
        "notes": lambda m: m.evaluation_notes.casefold(),
    }
    action_sort_fields = {
        "plan": "description", "realization": "realization",
        "target_date": "target_date", "owner": "responsible_person",
    }
    sort_key = request.GET.get("sort", "")
    direction = "desc" if request.GET.get("order") == "desc" else "asc"
    if sort_key in action_sort_fields:
        attribute = action_sort_fields[sort_key]
        def action_value(action):
            value = getattr(action, attribute)
            return value.casefold() if isinstance(value, str) else value
        for monitoring in monitorings:
            plans = list(monitoring.action_plans.all())
            present = [a for a in plans if action_value(a) is not None]
            missing = [a for a in plans if action_value(a) is None]
            present.sort(key=action_value, reverse=direction == "desc")
            monitoring._prefetched_objects_cache["action_plans"] = present + missing
        sort_fields[sort_key] = lambda m: next(
            (action_value(a) for a in m.action_plans.all() if action_value(a) is not None), None
        )
    if sort_key in sort_fields:
        value = sort_fields[sort_key]
        present = [m for m in monitorings if value(m) is not None]
        missing = [m for m in monitorings if value(m) is None]
        present.sort(key=lambda m: (value(m), m.pk), reverse=direction == "desc")
        monitorings = present + missing
    else:
        sort_key = ""
    division_rows, totals = _monitoring_summary(monitorings)
    priority_risks = sorted(
        [item for item in monitorings if item.final_level in {"Tinggi", "Sangat Tinggi"}],
        key=lambda item: (-LEVEL_ORDER.index(item.final_level), item.risk.risk_code),
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
    response = render(request, "risk_management/monitoring_report.html", {
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
        "monitorings": monitorings,
        "sorting_enabled": True, "sort_key": sort_key, "sort_order": direction,
    })
    _log(
        request, "MONITORING_REPORT_VIEWED", f"Membuka laporan pemantauan Triwulan {quarter} tahun {year}.",
        target_label=f"Pemantauan TW{quarter} {year}",
        metadata={"year": year, "quarter": quarter, "division": division,
                  "sort": sort_key, "order": direction, "risk_count": len(monitorings)},
    )
    return response


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
            _log(
                request,
                "MONITORING_CREATED",
                f"Menambahkan pemantauan {monitoring.get_quarter_display()} {monitoring.year}.",
                monitoring,
                target_label=risk.risk_code,
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
            _log(
                request,
                "MONITORING_UPDATED",
                f"Memperbarui pemantauan {monitoring.get_quarter_display()} {monitoring.year}.",
                monitoring,
                target_label=monitoring.risk.risk_code,
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
        _log(
            request,
            "ACTION_PLAN_CREATED",
            "Menambahkan rencana aksi pemantauan.",
            action,
            target_label=monitoring.risk.risk_code,
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
        _log(
            request,
            "ACTION_PLAN_UPDATED",
            "Memperbarui rencana aksi dan realisasi.",
            action,
            target_label=risk.risk_code,
        )
        messages.success(request, "Rencana aksi berhasil diperbarui.")
        return redirect("risk:risk_detail", pk=risk.pk)
    return render(request, "risk_management/action_form.html", {
        "form": form, "monitoring": action.monitoring, "action": action,
        "page_title": "Edit Rencana Aksi dan Realisasi",
    })
