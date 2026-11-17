from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.forms import BaseInlineFormSet, formset_factory, inlineformset_factory

from .access import MANAGER_ROLES, accesses_for_user, risks_for_user
from .models import RiskAccess, RiskActionPlan, RiskDivision, RiskMonitoring, RiskRegister, RiskTreatment


class RiskTreatmentForm(forms.ModelForm):
    class Meta:
        model = RiskTreatment
        fields = ["risk", "option", "action_plan", "expected_likelihood", "expected_impact",
                  "target_date", "responsible_person", "notes"]
        labels = {"risk": "Nama Risiko"}
        widgets = {
            "option": forms.Textarea(attrs={"rows": 4}),
            "action_plan": forms.Textarea(attrs={"rows": 4}),
            "notes": forms.Textarea(attrs={"rows": 4}),
            "target_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "expected_likelihood": forms.NumberInput(attrs={"min": 1, "max": 5}),
            "expected_impact": forms.NumberInput(attrs={"min": 1, "max": 5}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if "risk" in self.fields:
            risks = risks_for_user(user)
            accesses = accesses_for_user(user)
            if not user.is_superuser and not accesses.filter(role__in=MANAGER_ROLES).exists():
                risks = risks.filter(division_id__in=accesses.filter(role="risk_officer").values_list("division_id", flat=True))
            self.fields["risk"].queryset = risks.order_by("risk_code")
            self.fields["risk"].disabled = bool(self.instance.pk)
        for field in self.fields.values():
            field.widget.attrs["class"] = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm"

    def clean(self):
        cleaned = super().clean()
        likelihood, impact = cleaned.get("expected_likelihood"), cleaned.get("expected_impact")
        if (likelihood is None) != (impact is None):
            self.add_error("expected_likelihood" if likelihood is None else "expected_impact",
                           "Isi kemungkinan dan dampak bersama-sama untuk menghitung risiko yang diharapkan.")
        return cleaned


class RiskTreatmentInlineForm(RiskTreatmentForm):
    risk_index = forms.IntegerField(required=False, min_value=0, widget=forms.HiddenInput)

    class Meta(RiskTreatmentForm.Meta):
        fields = ["option", "action_plan", "expected_likelihood", "expected_impact",
                  "target_date", "responsible_person", "notes"]


class BaseRiskTreatmentFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in self.forms:
            treatment = form.cleaned_data.get("id") if hasattr(form, "cleaned_data") else None
            if treatment is not None and treatment.risk_id != self.instance.pk:
                raise forms.ValidationError("Perlakuan risiko tidak sesuai dengan risiko yang sedang diedit.")


RiskTreatmentFormSet = inlineformset_factory(
    RiskRegister, RiskTreatment, form=RiskTreatmentInlineForm,
    formset=BaseRiskTreatmentFormSet, extra=1, can_delete=True,
    max_num=100, validate_max=True, absolute_max=200,
)


def pic_name(user):
    return user.get_full_name().strip() or user.get_username()


def division_pic_users(division):
    rows = RiskAccess.objects.filter(
        division=division, role__in=("risk_officer", "division_head", "staff_it", "staff_hrd", "staff_humas"),
        is_active=True, user__is_active=True,
    ).select_related("user").order_by("pk")
    users = {role: None for role in ("risk_officer", "division_head", "staff_it", "staff_hrd", "staff_humas")}
    for row in rows:
        if users[row.role] is None:
            users[row.role] = row.user
    return users


class NamedUserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return pic_name(obj)


class DivisionPICForm(forms.Form):
    risk_officer = NamedUserChoiceField(label="Risk Officer", queryset=get_user_model().objects.none())
    risk_owner = NamedUserChoiceField(label="Risk Owner", queryset=get_user_model().objects.none())
    staff_it = NamedUserChoiceField(label="Staff IT", queryset=get_user_model().objects.none(), required=False)
    staff_hrd = NamedUserChoiceField(label="HRD", queryset=get_user_model().objects.none(), required=False)
    staff_humas = NamedUserChoiceField(label="Humas", queryset=get_user_model().objects.none(), required=False)

    def __init__(self, *args, division, **kwargs):
        super().__init__(*args, **kwargs)
        current = division_pic_users(division)
        if division.code != "LUM":
            for name in ("staff_it", "staff_hrd", "staff_humas"):
                self.fields.pop(name)
        for name, role in (("risk_officer", "risk_officer"), ("risk_owner", "division_head"),
                           ("staff_it", "staff_it"), ("staff_hrd", "staff_hrd"),
                           ("staff_humas", "staff_humas")):
            if name not in self.fields:
                continue
            field = self.fields[name]
            field.queryset = get_user_model().objects.filter(is_active=True).order_by("first_name", "last_name", "username")
            field.initial = current[role].pk if current[role] else None
            field.widget.attrs["class"] = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm"


class AnnualRiskReportForm(forms.Form):
    year = forms.IntegerField(label="Tahun", min_value=2020, max_value=2100)
    division = forms.ModelChoiceField(
        label="Nama Divisi", queryset=RiskDivision.objects.none(),
        required=False, empty_label="Semua Divisi",
    )

    def __init__(self, *args, divisions, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["division"].queryset = divisions
        for field in self.fields.values():
            field.widget.attrs["class"] = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm"


class RiskWorkbookImportForm(forms.Form):
    workbook = forms.FileField(
        label="Workbook Manajemen Risiko",
        help_text="Pilih file .xlsx yang sudah diisi menggunakan template di halaman ini. Maksimal 10 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx", "class": "risk-import-file"}),
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
            "division", "risk_kind", "risk_source", "code_category", "title", "strategic_objective",
            "indication", "cause", "controllability", "impact",
            "inherent_likelihood", "inherent_impact", "existing_controls",
            "control_effectiveness", "is_priority",
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
            "division": "Nama Divisi", "title": "Nama Risiko",
            "risk_kind": "Jenis Risiko", "risk_source": "Sumber Risiko",
            "code_category": "Kategori Risiko",
            "strategic_objective": "Sasaran Terkait", "indication": "Indikasi Risiko",
            "cause": "Uraian", "controllability": "Controllable / Uncontrollable",
            "impact": "Dampak", "inherent_likelihood": "Kemungkinan",
            "inherent_impact": "Dampak", "residual_likelihood": "Kemungkinan",
            "residual_impact": "Dampak", "existing_controls": "Pengendalian yang Ada (Existing Control)",
            "control_effectiveness": "Efektivitas Pengendalian",
            "is_priority": "Nominasi Prioritas Risiko",
            "identification_notes": "Keterangan", "evaluation_notes": "Keterangan",
        }

    def __init__(self, *args, user=None, identification_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        current_division_id = self.instance.division_id if self.instance.pk else None
        self.fields["division"].queryset = RiskDivision.objects.filter(
            Q(is_active=True) | Q(pk=current_division_id)
        )
        common = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm focus:border-blue-600 focus:outline-none focus:ring-4 focus:ring-blue-100"
        for field in self.fields.values():
            field.widget.attrs["class"] = common
        for name in ("inherent_likelihood", "inherent_impact", "residual_likelihood", "residual_impact"):
            self.fields[name].widget.attrs.update({"min": 1, "max": 5, "step": 1})
        self.fields["is_priority"].widget.attrs["class"] = "h-5 w-5 rounded border-slate-300"
        self.fields["control_effectiveness"].widget.attrs["class"] = "space-y-3"
        self.fields["control_effectiveness"].choices = RiskRegister.CONTROL_EFFECTIVENESS_CHOICES[1:]
        if identification_only:
            for name in ("existing_controls", "control_effectiveness", "is_priority",
                         "residual_likelihood", "residual_impact", "evaluation_notes"):
                self.fields[name].disabled = True
        accesses = accesses_for_user(user) if user else None
        if accesses is not None and accesses.exists() and not accesses.filter(
            role__in=MANAGER_ROLES
        ).exists():
            division_ids = list(
                accesses.filter(role="risk_officer").exclude(division__isnull=True)
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

    def clean(self):
        cleaned = super().clean()
        for likelihood, impact in (("inherent_likelihood", "inherent_impact"),
                                   ("residual_likelihood", "residual_impact")):
            if (cleaned.get(likelihood) is None) != (cleaned.get(impact) is None):
                self.add_error(impact if cleaned.get(impact) is None else likelihood,
                               "Isi kemungkinan dan dampak bersama, atau kosongkan keduanya.")
        division = cleaned.get("division")
        kind = cleaned.get("risk_kind")
        if kind == "A" and not cleaned.get("risk_source"):
            self.add_error("risk_source", "Pilih kode sumber risiko strategis 01 atau 02.")
        if division and kind == "C" and division.code != "KSO":
            self.add_error("division", "Risiko proyek harus memakai divisi KSO.")
        if division and kind == "B" and division.code == "KSO":
            self.add_error("risk_kind", "Divisi KSO harus memakai jenis risiko Proyek.")
        if division:
            self.pic_users = division_pic_users(division)
            if not self.instance.pk or self.instance.division_id != division.pk:
                missing = [label for role, label in (("division_head", "Risk Owner"), ("risk_officer", "Risk Officer"))
                           if self.pic_users[role] is None]
                if missing:
                    self.add_error("division", "Tetapkan %s untuk divisi ini di Divisi & Penanggung Jawab." % " dan ".join(missing))
        return cleaned

    def save(self, commit=True):
        risk = super().save(commit=False)
        users = getattr(self, "pic_users", {})
        if users.get("division_head"):
            risk.risk_owner = pic_name(users["division_head"])
        if users.get("risk_officer"):
            risk.risk_officer = pic_name(users["risk_officer"])
        if not risk.pk:
            risk.category = "strategic" if risk.risk_kind == "A" else "operational"
            risk.description = self.cleaned_data.get("indication") or risk.title
        if commit:
            risk.save()
            self.save_m2m()
        return risk


AdditionalRiskFormSet = formset_factory(
    RiskRegisterForm, extra=0, can_delete=True, max_num=99, validate_max=True, absolute_max=100,
)


class AdditionalCauseForm(forms.Form):
    risk_index = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    description = forms.CharField(label="Uraian", widget=forms.Textarea(attrs={"rows": 3}))
    controllability = forms.ChoiceField(
        label="Controllable / Uncontrollable",
        choices=RiskRegister.CONTROLLABILITY_CHOICES, required=False,
    )
    impact = forms.CharField(label="Dampak", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    inherent_likelihood = forms.IntegerField(label="Kemungkinan", min_value=1, max_value=5,
                                             required=False, widget=forms.HiddenInput)
    inherent_impact = forms.IntegerField(label="Dampak inheren", min_value=1, max_value=5,
                                         required=False, widget=forms.HiddenInput)
    identification_notes = forms.CharField(label="Keterangan", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm"


AdditionalCauseFormSet = formset_factory(
    AdditionalCauseForm, extra=0, can_delete=True, max_num=99,
    validate_max=True, absolute_max=100,
)


class AdditionalControlForm(forms.Form):
    risk_index = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    description = forms.CharField(label="Pengendalian yang Ada", widget=forms.Textarea(attrs={"rows": 3}))
    effectiveness = forms.ChoiceField(
        label="Efektivitas Pengendalian",
        choices=RiskRegister.CONTROL_EFFECTIVENESS_CHOICES[1:],
        widget=forms.RadioSelect, required=False,
    )
    notes = forms.CharField(label="Keterangan", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = (
                "h-4 w-4 border-slate-300" if name == "effectiveness"
                else "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm"
            )


AdditionalControlFormSet = formset_factory(
    AdditionalControlForm, extra=0, can_delete=True, max_num=99,
    validate_max=True, absolute_max=100,
)


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


class RiskMonitoringExcelForm(RiskMonitoringForm):
    class Meta(RiskMonitoringForm.Meta):
        fields = [
            "year", "quarter", "initial_likelihood", "initial_impact",
            "final_likelihood", "final_impact", "expected_likelihood",
            "expected_impact", "evaluation_notes",
        ]
        labels = {"evaluation_notes": "Keterangan"}
        widgets = {"evaluation_notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance.pk and self.instance.business_environment_changes:
            self.initial["evaluation_notes"] = "\n".join(filter(None, [
                self.instance.evaluation_notes, self.instance.business_environment_changes,
            ]))

    def save(self, commit=True):
        monitoring = super().save(commit=False)
        monitoring.business_environment_changes = ""
        if commit:
            monitoring.save()
            self.save_m2m()
        return monitoring


class MonitoringExcelActionForm(forms.ModelForm):
    class Meta:
        model = RiskActionPlan
        fields = ["treatment", "description", "realization", "target_date", "responsible_person"]
        widgets = {
            "treatment": forms.HiddenInput(),
            "description": forms.Textarea(attrs={"rows": 2}),
            "realization": forms.Textarea(attrs={"rows": 2}),
            "target_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, risk=None, **kwargs):
        super().__init__(*args, **kwargs)
        if risk is not None:
            self.fields["treatment"].queryset = risk.treatments.all()
        treatment_value = self.instance.treatment_id or self.initial.get("treatment") or self.data.get(
            self.add_prefix("treatment")
        )
        self.is_treatment_linked = bool(treatment_value)
        if self.instance.treatment_id and not self.is_bound:
            self.initial["description"] = self.instance.treatment.action_plan
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm "
                "focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100"
            )
        if self.is_treatment_linked:
            self.fields["description"].widget.attrs["readonly"] = True

    def clean(self):
        cleaned = super().clean()
        treatment = cleaned.get("treatment")
        if self.instance.pk and self.instance.treatment_id and (
            treatment is None or treatment.pk != self.instance.treatment_id
        ):
            self.add_error("treatment", "Rencana perlakuan yang sudah terhubung tidak dapat diganti di pemantauan.")
        if treatment:
            cleaned["description"] = treatment.action_plan
        return cleaned


class BaseMonitoringExcelActionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen_treatments = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            treatment = form.cleaned_data.get("treatment")
            if form.cleaned_data.get("DELETE"):
                if treatment or form.instance.treatment_id:
                    raise forms.ValidationError("Baris dari Perlakuan Risiko dikelola melalui bagian Perlakuan Risiko.")
                continue
            if treatment:
                if treatment.pk in seen_treatments:
                    raise forms.ValidationError("Setiap perlakuan risiko hanya boleh muncul sekali dalam satu triwulan.")
                seen_treatments.add(treatment.pk)


MonitoringExcelActionFormSet = inlineformset_factory(
    RiskMonitoring, RiskActionPlan, form=MonitoringExcelActionForm,
    formset=BaseMonitoringExcelActionFormSet, extra=0, can_delete=True,
)


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
        if self.instance.pk and self.instance.treatment_id:
            self.fields["description"].disabled = True
            self.initial["description"] = self.instance.treatment.action_plan
            self.fields["description"].help_text = "Rencana ini mengikuti Perlakuan Risiko dan diubah dari sana."
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
