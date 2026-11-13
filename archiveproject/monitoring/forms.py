from django import forms
from django.contrib.auth import get_user_model

from .models import Assignment


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
