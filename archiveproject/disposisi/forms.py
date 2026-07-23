from django import forms
from django.utils.html import escape, strip_tags
from datetime import date
from html.parser import HTMLParser
import re
from .models import Disposisi

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


class DisposisiRichTextSanitizer(HTMLParser):
    """Keep the small formatting subset supported by the disposition editor."""

    allowed_tags = {
        "p", "div", "br", "strong", "b", "em", "i", "u",
        "ul", "ol", "li", "blockquote", "h2", "h3", "svg", "path",
    }
    blocked_tags = {"script", "style", "iframe", "object", "embed"}
    alignment_pattern = re.compile(
        r"^\s*text-align\s*:\s*(left|center|right|justify)\s*;?\s*$",
        re.IGNORECASE,
    )
    signature_path_pattern = re.compile(r"^[MLml0-9.,\s-]+$")
    signature_viewbox_pattern = re.compile(
        r"^0(?:\.0+)?\s+0(?:\.0+)?\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)$"
    )

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.blocked_depth = 0
        self.inside_signature = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.blocked_tags:
            self.blocked_depth += 1
            return
        if self.blocked_depth or tag not in self.allowed_tags:
            return

        if tag == "svg":
            attribute_map = {name: value for name, value in attrs}
            viewbox_match = self.signature_viewbox_pattern.fullmatch(
                (attribute_map.get("viewbox") or "").strip()
            )
            if (
                not self.inside_signature
                and attribute_map.get("data-signature-overlay") == "true"
                and viewbox_match
            ):
                width = float(viewbox_match.group(1))
                height = float(viewbox_match.group(2))
                if not (100 <= width <= 4000 and 100 <= height <= 4000):
                    return
                self.parts.append(
                    f'<svg viewBox="0 0 {width:g} {height:g}" '
                    'data-signature-overlay="true" preserveAspectRatio="xMidYMax meet" role="img" '
                    'aria-label="Tanda tangan digital">'
                )
                self.inside_signature = True
            return

        if tag == "path":
            path_data = next((value for name, value in attrs if name == "d"), "")
            if (
                self.inside_signature
                and 0 < len(path_data) <= 20000
                and self.signature_path_pattern.fullmatch(path_data)
            ):
                self.parts.append(
                    f'<path d="{path_data}" fill="none" stroke="#111827" '
                    'stroke-width="3" stroke-linecap="round" '
                    'stroke-linejoin="round" />'
                )
            return

        if self.inside_signature:
            return

        safe_attributes = ""
        if tag in {"p", "div", "h2", "h3", "blockquote"}:
            style = next((value for name, value in attrs if name == "style"), "")
            match = self.alignment_pattern.fullmatch(style or "")
            if match:
                safe_attributes = f' style="text-align: {match.group(1).lower()}"'

        self.parts.append(f"<{tag}{safe_attributes}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.blocked_tags:
            if self.blocked_depth:
                self.blocked_depth -= 1
            return
        if tag == "path":
            return
        if tag == "svg":
            if self.inside_signature:
                self.parts.append("</svg>")
                self.inside_signature = False
            return
        if self.inside_signature:
            return
        if not self.blocked_depth and tag in self.allowed_tags and tag != "br":
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.blocked_depth and not self.inside_signature:
            self.parts.append(escape(data))

    def get_html(self):
        if self.inside_signature:
            self.parts.append("</svg>")
            self.inside_signature = False
        return "".join(self.parts).strip()


def sanitize_disposisi_rich_text(value):
    sanitizer = DisposisiRichTextSanitizer()
    sanitizer.feed(value or "")
    sanitizer.close()
    return sanitizer.get_html()


def validate_uploaded_document(uploaded_file):
    if not uploaded_file:
        return uploaded_file

    if uploaded_file.size > MAX_UPLOAD_SIZE:
        raise forms.ValidationError("Ukuran maksimal file adalah 10 MB.")

    content_type = getattr(uploaded_file, "content_type", None)
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise forms.ValidationError("Format file tidak diizinkan (PDF / JPG / PNG).")

    return uploaded_file

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
            "dokumen_surat_masuk",
            "dokumen_disposisi"
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

        return validate_uploaded_document(file)

    def clean_dokumen_disposisi(self):
        return validate_uploaded_document(
            self.cleaned_data.get("dokumen_disposisi")
        )

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


class DisposisiUploadForm(forms.ModelForm):
    class Meta:
        model = Disposisi
        fields = ["dokumen_disposisi"]

    def clean_dokumen_disposisi(self):
        return validate_uploaded_document(
            self.cleaned_data.get("dokumen_disposisi")
        )


class OnlineDisposisiIsiForm(forms.ModelForm):
    class Meta:
        model = Disposisi
        fields = ["isi_disposisi"]
        widgets = {"isi_disposisi": forms.HiddenInput()}

    def clean_isi_disposisi(self):
        raw_content = self.cleaned_data.get("isi_disposisi", "")
        if len(raw_content) > 200000:
            raise forms.ValidationError("Isi disposisi terlalu besar.")

        content = sanitize_disposisi_rich_text(raw_content)
        layout_text = re.sub(
            r"<br\s*/?>|</(?:p|div|li|blockquote|h2|h3)>",
            "\n",
            content,
            flags=re.IGNORECASE,
        )
        visible_text = strip_tags(layout_text).replace("&nbsp;", "").strip()
        if not visible_text and "<svg " not in content:
            raise forms.ValidationError("Isi disposisi wajib diisi sebelum dikirim.")
        layout_units = len(visible_text) + (visible_text.count("\n") * 60)
        if layout_units > 2400:
            raise forms.ValidationError(
                "Isi disposisi melebihi batas satu halaman A4. Kurangi teks."
            )
        return content


class ShareDisposisiForm(forms.Form):
    recipients = forms.MultipleChoiceField(
        label="Tujuan Bagikan",
        choices=Disposisi.SHARE_ROLE_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={
            "class": "mt-1 h-4 w-4 accent-blue-900",
        }),
        error_messages={
            "required": "Pilih minimal satu tujuan disposisi.",
            "invalid_choice": "Tujuan disposisi tidak valid.",
        },
    )

