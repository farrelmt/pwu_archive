from django import template
from django.utils.safestring import mark_safe
import re

register = template.Library()

HARI_ID = [
    '', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', "Sabtu", 'Minggu'
]

BULAN_ID = [
    '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
]

@register.filter
def tanggal_id(value):
    if not value:
        return ''
    return f"{value.day} {BULAN_ID[value.month]} {value.year}"

@register.filter
def hari_id(value):
    if not value:
        return ''
    return HARI_ID[value.weekday() + 1]


_SIGNATURE_RE = re.compile(
    r'<svg\s+(?P<attrs>[^>]*data-signature-overlay="true"[^>]*)>'
    r'(?P<body>.*?)</svg>',
    re.IGNORECASE | re.DOTALL,
)
_VIEWBOX_RE = re.compile(
    r'viewBox="0\s+0\s+[\d.]+\s+[\d.]+"',
    re.IGNORECASE,
)
_PATH_DATA_RE = re.compile(r'd="(?P<data>[MLml0-9.,\s-]+)"')


@register.filter
def normalize_signature_layout(value):
    """Render legacy full-page signatures at their original drawn size."""
    if not value:
        return ''

    def normalize_svg(match):
        attrs = match.group('attrs')
        body = match.group('body')
        if 'data-signature-layout="positioned"' in attrs:
            return match.group(0)
        if 'data-signature-layout="inline"' in attrs:
            values = {}
            for name in (
                'data-signature-width',
                'data-signature-height',
                'data-signature-origin-x',
                'data-signature-origin-y',
            ):
                value_match = re.search(
                    rf'{name}="([\d.]+)"',
                    attrs,
                    flags=re.IGNORECASE,
                )
                if value_match is None:
                    return match.group(0)
                values[name] = float(value_match.group(1))
            attrs = attrs.replace(
                'data-signature-layout="inline"',
                'data-signature-layout="positioned"',
            )
            attrs = re.sub(r'\s+style="[^"]*"', '', attrs)
            attrs += (
                f' style="position: absolute; '
                f'width: {values["data-signature-width"]:g}px; '
                f'height: {values["data-signature-height"]:g}px; '
                f'left: {values["data-signature-origin-x"]:g}px; '
                f'top: {values["data-signature-origin-y"]:g}px"'
            )
            return f'<svg {attrs}>{body}</svg>'

        parsed_paths = []
        all_points = []
        for path_match in _PATH_DATA_RE.finditer(body):
            tokens = re.findall(
                r'[MLml]|-?\d+(?:\.\d+)?',
                path_match.group('data'),
            )
            points = []
            for index in range(0, len(tokens) - 2, 3):
                try:
                    point = (
                        tokens[index],
                        float(tokens[index + 1]),
                        float(tokens[index + 2]),
                    )
                except (TypeError, ValueError):
                    continue
                points.append(point)
                all_points.append(point[1:])
            parsed_paths.append((path_match, points))

        if not all_points:
            return match.group(0)

        padding = 6
        minimum_x = max(0, min(point[0] for point in all_points) - padding)
        minimum_y = max(0, min(point[1] for point in all_points) - padding)
        maximum_x = max(point[0] for point in all_points) + padding
        maximum_y = max(point[1] for point in all_points) + padding
        width = max(10, maximum_x - minimum_x)
        height = max(10, maximum_y - minimum_y)

        rebuilt_body = body
        for path_match, points in reversed(parsed_paths):
            if not points:
                continue
            path_data = ' '.join(
                f'{command} {x - minimum_x:g} {y - minimum_y:g}'
                for command, x, y in points
            )
            start, end = path_match.span('data')
            rebuilt_body = (
                rebuilt_body[:start]
                + path_data
                + rebuilt_body[end:]
            )

        attrs = _VIEWBOX_RE.sub(
            f'viewBox="0 0 {width:g} {height:g}"',
            attrs,
        )
        attrs = re.sub(
            r'\s+preserveAspectRatio="[^"]*"',
            '',
            attrs,
            flags=re.IGNORECASE,
        )
        inline_attrs = (
            ' data-signature-layout="positioned"'
            f' data-signature-width="{width:g}"'
            f' data-signature-height="{height:g}"'
            f' data-signature-margin-left="{minimum_x:g}"'
            ' data-signature-margin-top="8"'
            f' data-signature-origin-x="{minimum_x:g}"'
            f' data-signature-origin-y="{minimum_y:g}"'
            f' style="position: absolute; width: {width:g}px; '
            f'height: {height:g}px; left: {minimum_x:g}px; '
            f'top: {minimum_y:g}px"'
            ' preserveAspectRatio="xMinYMin meet"'
        )
        return f'<svg {attrs}{inline_attrs}>{rebuilt_body}</svg>'

    return mark_safe(_SIGNATURE_RE.sub(normalize_svg, str(value)))
