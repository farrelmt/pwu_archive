from django import forms
from django.contrib.auth import get_user_model

from .models import Assignment, ChecklistGroup, ChecklistItem


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ["title", "description", "month", "start_date", "due_date", "division", "responsible", "status"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "month": forms.DateInput(attrs={"type": "month"}, format="%Y-%m"),
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["month"].input_formats = ["%Y-%m", "%Y-%m-%d"]
        self.fields["responsible"].queryset = get_user_model().objects.filter(is_active=True).order_by(
            "first_name", "last_name", "username"
        )
        self.fields["responsible"].label_from_instance = (
            lambda user: f"{user.get_full_name().strip() or user.username} ({user.username})"
        )
        if self.instance.pk and not self.instance.responsible.is_active:
            self.fields["responsible"].queryset = get_user_model().objects.filter(
                pk=self.instance.responsible_id
            ) | self.fields["responsible"].queryset

    def clean_month(self):
        month = self.cleaned_data["month"]
        return month.replace(day=1)


class ChecklistStepsForm(forms.Form):
    steps = forms.CharField(
        label="Tugas checklist",
        widget=forms.Textarea(attrs={"rows": 3, "aria-label": "Tugas checklist baru"}),
    )

    def clean_steps(self):
        steps = [line.strip() for line in self.cleaned_data["steps"].splitlines() if line.strip()]
        if not steps:
            raise forms.ValidationError("Tulis minimal satu tugas checklist.")
        if len(steps) > 20:
            raise forms.ValidationError("Maksimal 20 tugas checklist sekali tambah.")
        if any(len(step) > 220 for step in steps):
            raise forms.ValidationError("Setiap tugas checklist maksimal 220 karakter.")
        return steps


class ChecklistItemEditForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ["text"]

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if not text:
            raise forms.ValidationError("Tugas checklist tidak boleh kosong.")
        return text


class ChecklistGroupForm(forms.ModelForm):
    class Meta:
        model = ChecklistGroup
        fields = ["title"]

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise forms.ValidationError("Judul checklist tidak boleh kosong.")
        return title
