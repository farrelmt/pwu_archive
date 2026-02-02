from django import forms
from datetime import date
from .models import Disposisi

class DisposisiForm(forms.ModelForm):

    class Meta:
        model = Disposisi
        fields = "__all__"

        widgets = {
            "tanggal_surat_diterima": forms.DateInput(attrs={"type": "date"}),
            "tanggal_surat": forms.DateInput(attrs={"type": "date"}),
            "perihal": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        tanggal_diterima = cleaned_data.get("tanggal_surat_diterima")
        tanggal_surat = cleaned_data.get("tanggal_surat")

        if tanggal_diterima and tanggal_surat:
            if tanggal_diterima < tanggal_surat:
                raise forms.ValidationError(
                    "Tanggal surat diterima tidak boleh lebih lama dari tanggal surat."
                )

        return cleaned_data