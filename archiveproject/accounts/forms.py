from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from inventory.models import InventoryAccess
from koperasi.models import KoperasiAccess
from risk_management.models import RiskAccess, RiskDivision


User = get_user_model()


class PersonalSettingsForm(forms.ModelForm):
    current_password = forms.CharField(
        label="Password saat ini",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_password = forms.CharField(
        label="Password baru",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    confirm_password = forms.CharField(
        label="Ulangi password baru",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone")
        labels = {
            "first_name": "Nama depan",
            "last_name": "Nama belakang",
            "email": "Email",
            "phone": "Nomor telepon",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 "
            "text-sm text-slate-900 outline-none transition focus:border-blue-500 "
            "focus:ring-4 focus:ring-blue-100"
        )
        for field in self.fields.values():
            field.widget.attrs.update({"class": input_class})

    def clean(self):
        cleaned = super().clean()
        current_password = cleaned.get("current_password")
        new_password = cleaned.get("new_password")
        confirmation = cleaned.get("confirm_password")
        wants_password_change = any((current_password, new_password, confirmation))
        if wants_password_change:
            if not current_password or not self.instance.check_password(current_password):
                self.add_error("current_password", "Password saat ini tidak benar.")
            if not new_password:
                self.add_error("new_password", "Password baru wajib diisi.")
            elif new_password != confirmation:
                self.add_error("confirm_password", "Password baru tidak sama.")
            else:
                try:
                    validate_password(new_password, user=self.instance)
                except ValidationError as error:
                    self.add_error("new_password", error)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("new_password"):
            user.set_password(self.cleaned_data["new_password"])
        if commit:
            user.save()
        return user


class MemberAccessForm(forms.ModelForm):
    password = forms.CharField(
        label="Password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Wajib untuk akun baru. Kosongkan saat mengedit jika tidak ingin mengganti password.",
    )
    password_confirm = forms.CharField(
        label="Ulangi password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    koperasi_roles = forms.MultipleChoiceField(
        label="Role Sistem Koperasi",
        choices=KoperasiAccess.ROLE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Kosongkan jika pengguna tidak memiliki akses Sistem Koperasi.",
    )
    risk_roles = forms.MultipleChoiceField(
        label="Role tambahan Manajemen Risiko",
        choices=RiskAccess.ROLE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            "Role ini melekat pada akun yang sama dan tidak menggantikan role "
            "Sistem Arsip, Koperasi, atau Inventaris."
        ),
    )
    risk_division = forms.ModelChoiceField(
        label="Divisi risiko",
        queryset=RiskDivision.objects.none(),
        required=False,
        empty_label="Semua divisi / tidak ditentukan",
    )
    inventory_role = forms.ChoiceField(
        label="Akses Sistem Inventaris",
        choices=InventoryAccess.ROLE_CHOICES,
        initial="participant",
    )

    class Meta:
        model = User
        fields = (
            "username", "first_name", "last_name", "email", "phone",
            "role", "is_active",
        )
        labels = {
            "username": "Username",
            "first_name": "Nama depan",
            "last_name": "Nama belakang",
            "email": "Email",
            "phone": "Nomor telepon",
            "role": "Role Sistem Arsip",
            "is_active": "Akun aktif",
        }

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.fields["risk_division"].queryset = RiskDivision.objects.filter(
            is_active=True
        ).order_by("name")
        self.fields["role"].required = False
        self.fields["role"].choices = [
            ("", "Tidak ada akses Sistem Arsip"),
            *[
                (
                    value,
                    "Pegawai (tanpa akses Sistem Arsip)" if value == "employee" else label,
                )
                for value, label in User.ROLE_CHOICES
            ],
        ]

        if self.instance.pk:
            koperasi_roles = list(self.instance.koperasi_accesses.filter(
                company__isnull=True, is_active=True
            ).values_list("role", flat=True))
            risk_accesses = list(self.instance.risk_accesses.filter(is_active=True))
            risk_division = next(
                (access.division_id for access in risk_accesses if access.division_id),
                None,
            )
            try:
                inventory_access = self.instance.inventory_access
            except InventoryAccess.DoesNotExist:
                inventory_access = None
            self.initial.update({
                "koperasi_roles": koperasi_roles,
                "risk_roles": [access.role for access in risk_accesses],
                "risk_division": risk_division,
                "inventory_role": inventory_access.role if inventory_access else "participant",
            })

        input_class = (
            "mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 "
            "text-sm text-slate-900 outline-none transition focus:border-blue-500 "
            "focus:ring-4 focus:ring-blue-100"
        )
        for field_name, field in self.fields.items():
            if field_name == "is_active":
                field.widget.attrs.update({"class": "h-5 w-5 rounded border-slate-300 text-blue-700"})
            elif isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs.update({"class": "role-check-grid"})
            else:
                field.widget.attrs.update({"class": input_class})

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirmation = cleaned.get("password_confirm")
        if not self.instance.pk and not password:
            self.add_error("password", "Password wajib diisi untuk akun baru.")
        if password != confirmation:
            self.add_error("password_confirm", "Password tidak sama.")
        if (
            set(cleaned.get("risk_roles") or []).intersection({"risk_officer", "division_head"})
            and not cleaned.get("risk_division")
        ):
            self.add_error("risk_division", "Divisi wajib dipilih untuk role risiko ini.")
        if self.instance.pk and self.actor == self.instance and not cleaned.get("is_active"):
            self.add_error("is_active", "Anda tidak dapat menonaktifkan akun sendiri.")
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        if not commit:
            return user

        user.save()
        self.save_m2m()
        user.koperasi_accesses.filter(company__isnull=True).delete()
        KoperasiAccess.objects.bulk_create([
            KoperasiAccess(user=user, company=None, role=role, is_active=True)
            for role in self.cleaned_data["koperasi_roles"]
        ])
        risk_roles = self.cleaned_data["risk_roles"]
        risk_division = self.cleaned_data.get("risk_division")
        user.risk_accesses.all().delete()
        RiskAccess.objects.bulk_create([
            RiskAccess(
                user=user,
                role=role,
                division=(risk_division if role in {"risk_officer", "division_head"} else None),
                is_active=True,
            )
            for role in risk_roles
        ])
        InventoryAccess.objects.update_or_create(
            user=user,
            defaults={"role": self.cleaned_data["inventory_role"], "is_active": True},
        )
        return user
