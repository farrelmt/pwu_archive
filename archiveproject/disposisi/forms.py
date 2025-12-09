from django import forms
from datetime import date
from .models import Disposisi

class DisposisiForm(forms.ModelForm):
    dd_tsd = forms.CharField(required=True)
    mm_tsd = forms.CharField(required=True)
    yy_tsd = forms.CharField(required=True)

    dd_ts = forms.CharField(required=True)
    mm_ts = forms.CharField(required=True)
    yy_ts = forms.CharField(required=True)

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
            "tanggal_surat_diterima": forms.DateInput(attrs={
                "type": "date",
                "class": "border rounded px-2 h-6 text-sm w-35 text-center"
            }),
            "tanggal_surat": forms.DateInput(attrs={"type": "date"}),
            "perihal": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned_data = super().clean()

        dd = self.data.get("dd_tsd")
        mm = self.data.get("mm_tsd")
        yy = self.data.get("yy_tsd")

        # Tanggal Surat Diterima
        try:
            cleaned_data["tanggal_surat_diterima"] = date(
                int(self.data["yy_tsd"]),
                int(self.data["mm_tsd"]),
                int(self.data["dd_tsd"]),
            )
        except ValueError:
            raise forms.ValidationError(
                "Tanggal Surat Diterima tidak valid"
            )

        # Tanggal Surat
        try:
            cleaned_data["tanggal_surat"] = date(
                int(self.data["yy_ts"]),
                int(self.data["mm_ts"]),
                int(self.data["dd_ts"]),
            )
        except:
            raise forms.ValidationError("Tanggal Surat tidak valid")

        return cleaned_data