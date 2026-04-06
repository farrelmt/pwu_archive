from django import template

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