from django import template

register = template.Library()

BULAN_ID = [
    '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
]

@register.filter
def tanggal_id(value):
    if not value:
        return ''
    return f"{value.day} {BULAN_ID[value.month]} {value.year}"
