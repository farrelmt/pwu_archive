from django import forms
from datetime import date
from .models import Disposisi

class DisposisiForm(forms.ModelForm):

    class Meta:
        model = Disposisi
        fields = [
            "tanggal_surat_diterima",
            #"nomor_agenda",
            "tanggal_surat",
            "nomor_surat",
            "pengirim",
            "lampiran",
            "tujuan",
            "tembusan",
            "perihal",
            "dokumen_surat_masuk"
        ]

        widgets = {
            "tanggal_surat_diterima": forms.DateInput(attrs={"type": "date"}),
            "tanggal_surat": forms.DateInput(attrs={"type": "date"}),
            "perihal": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_dokumen_surat_masuk(self):
        file = self.cleaned_data.get('dokumen_surat_masuk')

        if file and not file.name.lower().endswith(
                ('.pdf', '.jpg', '.jpeg', '.png')
        ):
            raise forms.ValidationError(
                "Format file tidak diizinkan (PDF / JPG / PNG)."
            )

        return file

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