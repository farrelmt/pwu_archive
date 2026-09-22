from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.utils.html import escape, strip_tags
from django.utils import timezone
from datetime import date
from html.parser import HTMLParser
import re
from PIL import Image, UnidentifiedImageError
from .models import Disposisi

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG"}


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
                signature_layout = attribute_map.get("data-signature-layout")
                is_positioned = signature_layout in {"inline", "positioned"}
                minimum_size = 10 if is_positioned else 100
                if not (
                    minimum_size <= width <= 4000
                    and minimum_size <= height <= 4000
                ):
                    return
                inline_attributes = ""
                preserve_aspect_ratio = "xMidYMax meet"
                if is_positioned:
                    numeric_values = {}
                    for name in (
                        "data-signature-width",
                        "data-signature-height",
                        "data-signature-margin-left",
                        "data-signature-margin-top",
                        "data-signature-origin-x",
                        "data-signature-origin-y",
                    ):
                        try:
                            numeric_values[name] = float(attribute_map[name])
                        except (KeyError, TypeError, ValueError):
                            return
                    display_width = numeric_values["data-signature-width"]
                    display_height = numeric_values["data-signature-height"]
                    margin_left = numeric_values["data-signature-margin-left"]
                    margin_top = numeric_values["data-signature-margin-top"]
                    origin_x = numeric_values["data-signature-origin-x"]
                    origin_y = numeric_values["data-signature-origin-y"]
                    if not (
                        10 <= display_width <= 760
                        and 10 <= display_height <= 700
                        and 0 <= margin_left <= 760
                        and 0 <= margin_top <= 700
                        and 0 <= origin_x <= 4000
                        and 0 <= origin_y <= 4000
                    ):
                        return
                    preserve_aspect_ratio = "xMinYMin meet"
                    inline_attributes = (
                        ' data-signature-layout="positioned"'
                        f' data-signature-width="{display_width:g}"'
                        f' data-signature-height="{display_height:g}"'
                        f' data-signature-margin-left="{margin_left:g}"'
                        f' data-signature-margin-top="{margin_top:g}"'
                        f' data-signature-origin-x="{origin_x:g}"'
                        f' data-signature-origin-y="{origin_y:g}"'
                        f' style="position: absolute; width: {display_width:g}px; '
                        f'height: {display_height:g}px; left: {origin_x:g}px; '
                        f'top: {origin_y:g}px"'
                    )
                self.parts.append(
                    f'<svg viewBox="0 0 {width:g} {height:g}" '
                    'data-signature-overlay="true"'
                    f'{inline_attributes} preserveAspectRatio="{preserve_aspect_ratio}" role="img" '
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
    if not isinstance(uploaded_file, UploadedFile):
        return uploaded_file

    if uploaded_file.size > MAX_UPLOAD_SIZE:
        raise forms.ValidationError("Ukuran maksimal file adalah 10 MB.")

    content_type = getattr(uploaded_file, "content_type", None)
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise forms.ValidationError("Format file tidak diizinkan (PDF / JPG / PNG).")

    header = uploaded_file.read(8)
    uploaded_file.seek(0)
    if content_type == "application/pdf":
        if not header.startswith(b"%PDF-"):
            raise forms.ValidationError("Isi file bukan PDF yang valid.")
        return uploaded_file

    try:
        image = Image.open(uploaded_file)
        image.verify()
        image_format = image.format
    except (UnidentifiedImageError, OSError, ValueError):
        raise forms.ValidationError("Isi file gambar tidak valid.")
    finally:
        uploaded_file.seek(0)

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise forms.ValidationError("Format gambar tidak diizinkan.")
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
        labels = {
            "tanggal_surat_diterima": "Tanggal Surat Diterima",
            "tanggal_surat": "Tanggal Surat",
            "nomor_surat": "Nomor Surat",
            "pengirim": "Pengirim",
            "lampiran": "Lampiran",
            "tujuan": "Tujuan",
            "tembusan": "Tembusan",
            "perihal": "Perihal",
            "dokumen_surat_masuk": "Dokumen Surat Masuk",
        }
        error_messages = {
            "tanggal_surat_diterima": {
                "required": "Tanggal surat diterima wajib diisi.",
            },
            "tanggal_surat": {"required": "Tanggal surat wajib diisi."},
            "nomor_surat": {"required": "Nomor surat wajib diisi."},
            "pengirim": {"required": "Pengirim wajib diisi."},
            "lampiran": {"required": "Lampiran wajib diisi."},
            "tujuan": {"required": "Tujuan wajib dipilih."},
            "tembusan": {"required": "Tembusan wajib diisi."},
            "perihal": {"required": "Perihal wajib diisi."},
            "dokumen_surat_masuk": {
                "required": "Dokumen surat masuk wajib diunggah.",
            },
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
    def __init__(
        self,
        *args,
        max_layout_units=2400,
        require_signature=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.max_layout_units = max_layout_units
        self.require_signature = require_signature

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
        if self.require_signature and "<svg " not in content:
            raise forms.ValidationError(
                "Tanda tangan wajib digambar sebelum isi disposisi dikirim."
            )
        layout_units = len(visible_text) + (visible_text.count("\n") * 60)
        if layout_units > self.max_layout_units:
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
    deadline = forms.DateField(
        label="Deadline",
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}),
        error_messages={
            "required": "Deadline disposisi wajib dipilih.",
            "invalid": "Format deadline tidak valid.",
        },
    )

    def __init__(
        self,
        *args,
        choices=None,
        include_deadline=True,
        existing_deadline=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.existing_deadline = existing_deadline
        self.fields["recipients"].choices = (
            choices or Disposisi.ONLINE_SHARE_ROLE_CHOICES
        )
        if not include_deadline:
            self.fields.pop("deadline")

    def clean_deadline(self):
        deadline = self.cleaned_data["deadline"]
        if deadline < timezone.localdate() and deadline != self.existing_deadline:
            raise forms.ValidationError("Deadline tidak boleh sebelum hari ini.")
        return deadline


class RecipientActivityForm(forms.Form):
    activity_description = forms.CharField(
        label="Aktivitas yang Dilakukan",
        max_length=2000,
        strip=True,
        widget=forms.Textarea(attrs={
            "rows": 5,
            "placeholder": (
                "Jelaskan aktivitas atau tindak lanjut yang telah dilakukan."
            ),
        }),
        error_messages={
            "required": "Aktivitas wajib diisi sebelum disposisi diselesaikan.",
            "max_length": "Aktivitas maksimal 2.000 karakter.",
        },
    )
    follow_up_result = forms.CharField(
        label="Hasil Tindak Lanjut",
        max_length=2000,
        strip=True,
        widget=forms.Textarea(attrs={
            "rows": 5,
            "placeholder": "Jelaskan hasil dari tindak lanjut tersebut.",
        }),
        error_messages={
            "required": "Hasil tindak lanjut wajib diisi.",
            "max_length": "Hasil tindak lanjut maksimal 2.000 karakter.",
        },
    )
