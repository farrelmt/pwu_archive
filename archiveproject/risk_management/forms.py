from django import forms

from .access import MANAGER_ROLES, accesses_for_user
from .models import RiskActionPlan, RiskMonitoring, RiskRegister


class RiskRegisterForm(forms.ModelForm):
    class Meta:
        model = RiskRegister
        fields = [
            "division", "title", "category", "description", "cause", "impact",
            "inherent_likelihood", "inherent_impact", "existing_controls",
            "mitigation_plan", "risk_owner", "target_date",
            "residual_likelihood", "residual_impact", "status",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "cause": forms.Textarea(attrs={"rows": 3}),
            "impact": forms.Textarea(attrs={"rows": 3}),
            "existing_controls": forms.Textarea(attrs={"rows": 3}),
            "mitigation_plan": forms.Textarea(attrs={"rows": 4}),
            "target_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        common = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm focus:border-blue-600 focus:outline-none focus:ring-4 focus:ring-blue-100"
        for field in self.fields.values():
            field.widget.attrs["class"] = common
        accesses = accesses_for_user(user) if user else None
        if accesses is not None and accesses.exists() and not accesses.filter(
            role__in=MANAGER_ROLES
        ).exists():
            division_ids = list(
                accesses.exclude(division__isnull=True)
                .values_list("division_id", flat=True)
                .distinct()
            )
            self.fields["division"].queryset = self.fields["division"].queryset.filter(
                pk__in=division_ids
            )
            if division_ids:
                self.fields["division"].initial = division_ids[0]
            if len(division_ids) == 1:
                self.fields["division"].disabled = True

    def clean_division(self):
        return self.cleaned_data["division"]


class RiskMonitoringForm(forms.ModelForm):
    class Meta:
        model = RiskMonitoring
        fields = [
            "year", "quarter", "initial_likelihood", "initial_impact",
            "final_likelihood", "final_impact", "business_environment_changes",
            "evaluation_notes",
        ]
        widgets = {
            "business_environment_changes": forms.Textarea(attrs={"rows": 3}),
            "evaluation_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        common = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm focus:border-blue-600 focus:outline-none focus:ring-4 focus:ring-blue-100"
        for field in self.fields.values():
            field.widget.attrs["class"] = common
        self.fields["year"].widget.attrs.update({"min": 2020, "max": 2100})


class RiskActionPlanForm(forms.ModelForm):
    class Meta:
        model = RiskActionPlan
        fields = [
            "description", "responsible_person", "target_date", "realization",
            "realization_date", "progress", "status",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "target_date": forms.DateInput(attrs={"type": "date"}),
            "realization": forms.Textarea(attrs={"rows": 3}),
            "realization_date": forms.DateInput(attrs={"type": "date"}),
            "progress": forms.NumberInput(attrs={"min": 0, "max": 100}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        common = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm focus:border-blue-600 focus:outline-none focus:ring-4 focus:ring-blue-100"
        for field in self.fields.values():
            field.widget.attrs["class"] = common

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        realization = (cleaned.get("realization") or "").strip()
        realization_date = cleaned.get("realization_date")
        progress = cleaned.get("progress")
        if status == "completed":
            if not realization:
                self.add_error("realization", "Isi realisasi wajib diisi untuk aksi yang terealisasi.")
            if not realization_date:
                self.add_error("realization_date", "Tanggal realisasi wajib diisi.")
            cleaned["progress"] = 100
        elif progress == 100:
            self.add_error("status", "Pilih status Terealisasi untuk progres 100%.")
        return cleaned
