from django import forms
from PIL import Image, UnidentifiedImageError


MAX_SCREENSHOT_SIZE = 5 * 1024 * 1024
SCREENSHOT_FORMATS = {"JPEG", "PNG"}


class ReportForm(forms.Form):
    title = forms.CharField(max_length=120)
    description = forms.CharField(max_length=5000)
    steps = forms.CharField(max_length=5000)
    screenshot = forms.FileField(required=False)

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if "\r" in title or "\n" in title:
            raise forms.ValidationError("Judul tidak valid.")
        return title

    def clean_screenshot(self):
        screenshot = self.cleaned_data.get("screenshot")
        if not screenshot:
            return screenshot
        if screenshot.size > MAX_SCREENSHOT_SIZE:
            raise forms.ValidationError("Ukuran screenshot maksimal 5 MB.")

        try:
            image = Image.open(screenshot)
            image.verify()
            image_format = image.format
        except (UnidentifiedImageError, OSError, ValueError):
            raise forms.ValidationError("Screenshot harus berupa JPG atau PNG.")
        finally:
            screenshot.seek(0)

        if image_format not in SCREENSHOT_FORMATS:
            raise forms.ValidationError("Screenshot harus berupa JPG atau PNG.")
        screenshot.content_type = (
            "image/jpeg" if image_format == "JPEG" else "image/png"
        )
        return screenshot
