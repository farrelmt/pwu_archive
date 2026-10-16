from django import forms
from django.contrib.auth import get_user_model

from .access import MANAGER_ROLES, accesses_for_user
from .models import RiskAccess, RiskActionPlan, RiskDivision, RiskMonitoring, RiskRegister


class DivisionPICForm(forms.Form):
    risk_officers = forms.ModelMultipleChoiceField(label="Risk Officer", queryset=get_user_model().objects.none(), required=False)
    division_heads = forms.ModelMultipleChoiceField(label="Kepala Divisi", queryset=get_user_model().objects.none(), required=False)

    def __init__(self, *args, division, **kwargs):
        super().__init__(*args, **kwargs)
        for name, role in (("risk_officers", "risk_officer"), ("division_heads", "division_head")):
            field = self.fields[name]
            field.queryset = get_user_model().objects.filter(is_active=True).order_by("username")
            field.initial = list(RiskAccess.objects.filter(division=division, role=role, is_active=True).values_list("user_id", flat=True))
            field.widget.attrs.update({"class": "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm", "size": 8})


class AnnualRiskReportForm(forms.Form):
    year = forms.IntegerField(label="Tahun", min_value=2020, max_value=2100)
    division = forms.ModelChoiceField(label="Nama Divisi", queryset=RiskDivision.objects.none())

    def __init__(self, *args, divisions, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["division"].queryset = divisions
        for field in self.fields.values():
            field.widget.attrs["class"] = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm"


class RiskWorkbookImportForm(forms.Form):
    workbook = forms.FileField(
        label="Workbook Manajemen Risiko",
        help_text="Gunakan file .xlsx dengan struktur template Manajemen Risiko 2026.",
    )

    def clean_workbook(self):
        workbook = self.cleaned_data["workbook"]
        if not workbook.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("File harus berformat .xlsx.")
        if workbook.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Ukuran workbook maksimal 10 MB.")
        signature = workbook.read(4)
        workbook.seek(0)
        if signature != b"PK\x03\x04":
            raise forms.ValidationError("File bukan workbook Excel yang valid.")
        return workbook


class RiskRegisterForm(forms.ModelForm):
    class Meta:
        model = RiskRegister
        fields = [
            "division", "title", "strategic_objective",
            "indication", "cause", "controllability", "impact",
            "inherent_likelihood", "inherent_impact", "existing_controls",
            "control_effectiveness", "is_priority", "risk_owner", "risk_officer",
            "residual_likelihood", "residual_impact",
            "identification_notes", "evaluation_notes",
        ]
        widgets = {
            "strategic_objective": forms.Textarea(attrs={"rows": 3}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "indication": forms.Textarea(attrs={"rows": 3}),
            "cause": forms.Textarea(attrs={"rows": 3}),
            "impact": forms.Textarea(attrs={"rows": 3}),
            "existing_controls": forms.Textarea(attrs={"rows": 3}),
            "mitigation_plan": forms.Textarea(attrs={"rows": 4}),
            "target_date": forms.DateInput(attrs={"type": "date"}),
            "identification_notes": forms.Textarea(attrs={"rows": 3}),
            "evaluation_notes": forms.Textarea(attrs={"rows": 3}),
            "control_effectiveness": forms.RadioSelect(),
        }
        labels = {
            "division": "Nama Divisi", "risk_owner": "Risk Owner",
            "risk_officer": "Risk Officer", "title": "Nama Risiko",
            "strategic_objective": "Sasaran Terkait", "indication": "Indikasi Risiko",
            "cause": "Uraian", "controllability": "Controllable / Uncontrollable",
            "impact": "Dampak", "inherent_likelihood": "Kemungkinan",
            "inherent_impact": "Dampak", "residual_likelihood": "Kemungkinan",
            "residual_impact": "Dampak", "existing_controls": "Pengendalian yang Ada (Existing Control)",
            "control_effectiveness": "Efektivitas Pengendalian",
            "is_priority": "Nominasi Prioritas Risiko",
            "identification_notes": "Keterangan", "evaluation_notes": "Keterangan",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        common = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm focus:border-blue-600 focus:outline-none focus:ring-4 focus:ring-blue-100"
        for field in self.fields.values():
            field.widget.attrs["class"] = common
        self.fields["is_priority"].widget.attrs["class"] = "h-5 w-5 rounded border-slate-300"
        self.fields["control_effectiveness"].widget.attrs["class"] = "space-y-3"
        self.fields["control_effectiveness"].choices = RiskRegister.CONTROL_EFFECTIVENESS_CHOICES[1:]
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

    def save(self, commit=True):
        risk = super().save(commit=False)
        if not risk.pk:
            risk.category = "operational"
            risk.description = self.cleaned_data.get("indication") or risk.title
        if commit:
            risk.save()
            self.save_m2m()
        return risk


class RiskMonitoringForm(forms.ModelForm):
    class Meta:
        model = RiskMonitoring
        fields = [
            "year", "quarter", "initial_likelihood", "initial_impact",
            "final_likelihood", "final_impact", "business_environment_changes",
            "expected_likelihood", "expected_impact", "evaluation_notes",
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
