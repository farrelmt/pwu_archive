from uuid import uuid4
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ExpressionWrapper, F, IntegerField, Prefetch, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.activity_views import system_activity_log
from accounts.audit import record_activity

from .access import MANAGER_ROLES, can_edit_risk, can_manage_division_pic, risk_required, risk_write_required, risks_for_user
from .forms import (
    AnnualRiskReportForm,
    DivisionPICForm,
    RiskActionPlanForm,
    RiskMonitoringForm,
    RiskRegisterForm,
    RiskWorkbookImportForm,
)
from .models import (
    RiskActionPlan,
    RiskAccess,
    RiskActivity,
    RiskDivision,
    RiskMonitoring,
    RiskRegister,
)
from .services import import_risk_workbook
from .exports import annual_risk_workbook


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
    risks = risks_for_user(request.user).annotate(
        calculated_residual_score=ExpressionWrapper(
            F("residual_likelihood") * F("residual_impact"),
            output_field=IntegerField(),
        )
    )
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
        very_low=Count(
            "pk", filter=Q(calculated_residual_score__lt=3), distinct=True,
        ),
        low=Count(
            "pk",
            filter=Q(calculated_residual_score__gte=3, calculated_residual_score__lt=5),
            distinct=True,
        ),
        medium=Count(
            "pk",
            filter=Q(calculated_residual_score__gte=5, calculated_residual_score__lt=10),
            distinct=True,
        ),
        high=Count(
            "pk",
            filter=Q(calculated_residual_score__gte=10, calculated_residual_score__lt=17),
            distinct=True,
        ),
        very_high=Count(
            "pk", filter=Q(calculated_residual_score__gte=17), distinct=True,
        ),
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
        "category": "category", "inherent": "sort_inherent",
        "residual": "sort_residual", "status": "status",
    }
    sort_key = request.GET.get("sort", "")
    direction = "desc" if request.GET.get("order") == "desc" else "asc"
    if sort_key in sort_fields:
        risks = risks.annotate(
            sort_inherent=F("inherent_likelihood") * F("inherent_impact"),
            sort_residual=F("residual_likelihood") * F("residual_impact"),
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
    if category in dict(RiskRegister.CATEGORY_CHOICES):
        risks = risks.filter(category=category)
    if level:
        ids = [risk.pk for risk in risks if risk.risk_level.lower() == level.lower()]
        risks = risks.filter(pk__in=ids)
    page_obj = Paginator(risks, 20).get_page(request.GET.get("page"))
    visible_divisions = RiskDivision.objects.filter(risks__in=risks_for_user(request.user)).distinct()
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    response = render(request, "risk_management/risk_list.html", {
        "page_obj": page_obj, "divisions": visible_divisions,
        "available_years": available_years,
        "sorting_enabled": True, "sort_key": sort_key, "sort_order": direction,
        "pagination_query": pagination_params.urlencode(),
        "statuses": RiskRegister.STATUS_CHOICES, "categories": RiskRegister.CATEGORY_CHOICES,
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
                if access.division_id is not None
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
        risks = visible_risks.filter(division=division).filter(
            Q(created_at__year=year) | Q(monitorings__year=year)
        ).distinct().order_by("risk_code").prefetch_related(
            "treatments", Prefetch("monitorings", queryset=RiskMonitoring.objects.filter(
                year=year,
            ).prefetch_related("action_plans")),
        )
        if not risks.exists():
            form.add_error(None, "Tidak ada data risiko untuk tahun dan divisi yang dipilih.")
        else:
            download_mark = {
                "version": 1,
                "download_id": str(uuid4()),
                "user_id": str(request.user.pk),
                "username": request.user.get_username(),
                "full_name": request.user.get_full_name() or request.user.get_username(),
                "downloaded_at": timezone.now().astimezone(ZoneInfo("Asia/Jakarta")).isoformat(),
                "year": year,
                "division_id": division.pk,
            }
            try:
                workbook = annual_risk_workbook(risks, division=division, year=year, download_mark=download_mark)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                from django.utils.text import slugify
                filename = f"Manajemen Risiko {year} - {slugify(division.name)}.xlsx"
                response = FileResponse(
                    workbook, as_attachment=True, filename=filename,
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                response["Cache-Control"] = "private, no-store"
                _log(
                    request, "ANNUAL_REPORT_DOWNLOADED",
                    f"Menyiapkan unduhan laporan tahunan {year} untuk {division.name}: {filename}.",
                    division, target_label=filename,
                    metadata={
                        "year": year, "division_id": division.pk, "division": division.name,
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
    impact_levels = [
        (5, "Sangat Signifikan"), (4, "Signifikan"), (3, "Moderat"),
        (2, "Minor"), (1, "Tidak Signifikan"),
    ]
    matrix = [
        {"impact": impact, "cells": [
            {"score": impact * likelihood, "level": RiskRegister.level_for(impact * likelihood)}
            for likelihood in range(1, 6)
        ]}
        for impact in range(5, 0, -1)
    ]
    return render(request, "risk_management/scoring_guide.html", {
        "likelihoods": likelihoods,
        "impact_levels": impact_levels,
        "matrix": matrix,
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
    response = render(request, "risk_management/risk_detail.html", {
        "risk": risk, "can_edit_this": can_edit_risk(request.user, risk),
        "monitoring_tables": [(item, [item]) for item in risk.monitorings.all()],
    })
    _log(request, "RISK_VIEWED", f"Membuka detail risiko {risk.risk_code}.", risk, target_label=risk.risk_code)
    return response


@risk_write_required
def risk_create(request):
    form = RiskRegisterForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        risk = form.save(commit=False)
        risk.created_by = request.user
        risk.updated_by = request.user
        risk.save()
        RiskActivity.objects.create(risk=risk, actor=request.user, action="created", description="Risiko dibuat.")
        _log(request, "RISK_CREATED", "Menambahkan risiko baru.", risk, target_label=risk.risk_code)
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
        _log(
            request, "RISK_UPDATED", "Memperbarui data risiko.", risk, target_label=risk.risk_code,
            metadata={"changed_fields": [form.fields[name].label for name in form.changed_data]},
        )
        messages.success(request, f"{risk.risk_code} berhasil diperbarui.")
        return redirect("risk:risk_detail", pk=risk.pk)
    return render(request, "risk_management/risk_form.html", {"form": form, "risk": risk, "page_title": "Edit Risiko"})


@risk_required
def divisions(request):
    access_rows = RiskDivision.objects.prefetch_related(Prefetch(
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
    return render(request, "risk_management/divisions.html", {
        "divisions": access_rows, "can_manage_pic": can_manage_division_pic(request.user),
    })


@risk_required
def division_pic_edit(request, pk):
    if not can_manage_division_pic(request.user):
        raise PermissionDenied("Hanya Manajemen Risiko yang dapat mengubah PIC divisi.")
    division = get_object_or_404(RiskDivision, pk=pk, is_active=True)
    form = DivisionPICForm(request.POST if request.method == "POST" else None, division=division)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            division = RiskDivision.objects.select_for_update().get(pk=division.pk)
            before, after = {}, {}
            for name, role in (("risk_officers", "risk_officer"), ("division_heads", "division_head")):
                rows = RiskAccess.objects.filter(division=division, role=role)
                before[role] = sorted(rows.filter(is_active=True).values_list("user_id", flat=True))
                selected_ids = sorted(user.pk for user in form.cleaned_data[name])
                after[role] = selected_ids
                rows.exclude(user_id__in=selected_ids).filter(is_active=True).update(is_active=False)
                for user_id in selected_ids:
                    RiskAccess.objects.update_or_create(
                        division=division, role=role, user_id=user_id, defaults={"is_active": True},
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
        "initial_score": lambda m: m.initial_score,
        "final_likelihood": lambda m: m.final_likelihood,
        "final_impact": lambda m: m.final_impact,
        "final_score": lambda m: m.final_score,
        "expected_likelihood": lambda m: m.expected_likelihood,
        "expected_impact": lambda m: m.expected_impact,
        "expected_score": lambda m: m.expected_score,
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
        [item for item in monitorings if item.final_score >= 10],
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
