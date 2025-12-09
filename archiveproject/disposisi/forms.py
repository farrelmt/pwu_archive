from django import forms
from datetime import date
from .models import Disposisi

class DisposisiForm(forms.ModelForm):

    class Meta:
        model = Disposisi
        fields = [
            "tanggal_surat_diterima",
            "nomor_agenda",
            "tanggal_surat",
            "nomor_surat",
            "pengirim",
            "lampiran",
            "tujuan",
            "tembusan",
            "perihal",
            "diajukan_kepada",
            "dokumen_surat_masuk"
        ]

        widgets = {
            "tanggal_surat_diterima": forms.DateInput(attrs={"type": "date"}),
            "tanggal_surat": forms.DateInput(attrs={"type": "date"}),
            "perihal": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data