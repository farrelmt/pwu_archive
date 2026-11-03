from collections import Counter
from decimal import Decimal

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import InventoryItem


NAVY = "1E1B4B"
VIOLET = "6D28D9"
PALE = "F5F3FF"
SLATE = "475569"
WHITE = "FFFFFF"
CURRENCY_FORMAT = '"Rp" #,##0.00;[Red]("Rp" #,##0.00)'
DATE_FORMAT = "dd mmm yyyy"
DATETIME_FORMAT = "dd mmm yyyy hh:mm"

DETAIL_HEADERS = [
    "Kode Aset", "Nama Barang", "Kategori", "Merek", "Model/Tipe",
    "Nomor Seri/Lisensi", "Spesifikasi", "Tanggal Pembelian",
    "Tanggal Diterima", "Keterangan Tanggal Pembelian", "Kepemilikan",
    "Nama Pemilik Pihak Ketiga", "Kondisi", "Status Barang", "Jumlah",
    "Harga Satuan", "Nilai Total", "Pengguna/Penanggung Jawab",
    "Divisi Pengguna", "Lokasi", "Garansi Berakhir", "Catatan",
    "Dibuat", "Diperbarui",
]
DETAIL_WIDTHS = [
    24, 32, 26, 20, 22, 26, 45, 20, 20, 29, 18, 28,
    18, 20, 12, 20, 22, 32, 26, 24, 20, 45, 22, 22,
]


def safe_excel_text(value):
    """Keep user supplied text from becoming a spreadsheet formula."""
    value = str(value or "")[:32767]
    return "'" + value if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) else value


def local_excel_datetime(value):
    return timezone.localtime(value).replace(tzinfo=None) if value else None


def section_header(sheet, first_column, title):
    first = get_column_letter(first_column)
    last = get_column_letter(first_column + 1)
    sheet.merge_cells(f"{first}11:{last}11")
    cell = sheet.cell(11, first_column, title)
    cell.fill = PatternFill("solid", fgColor=NAVY)
    cell.font = Font(bold=True, color=WHITE, size=11)
    cell.alignment = Alignment(vertical="center")
    sheet.row_dimensions[11].height = 25


def build_inventory_workbook():
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Ringkasan"
    detail = workbook.create_sheet("Daftar Inventaris")
    summary.sheet_view.showGridLines = False
    detail.sheet_view.showGridLines = False

    generated_at = timezone.localtime()
    summary.merge_cells("A1:K2")
    title = summary["A1"]
    title.value = "LAPORAN INVENTARIS PWU JATIM"
    title.font = Font(name="Aptos Display", size=20, bold=True, color=WHITE)
    title.fill = PatternFill("solid", fgColor=NAVY)
    title.alignment = Alignment(vertical="center")
    summary.row_dimensions[1].height = 28
    summary.row_dimensions[2].height = 18
    summary.merge_cells("A3:K3")
    summary["A3"] = f"Seluruh barang inventaris • Dibuat {generated_at:%d %B %Y, %H:%M} WIB"
    summary["A3"].font = Font(name="Aptos", size=10, color=SLATE)
    summary.row_dimensions[3].height = 25
    for column in "ABCDEFGHIJK":
        summary.column_dimensions[column].width = 17

    detail.merge_cells("A1:X2")
    detail["A1"] = "DAFTAR LENGKAP BARANG INVENTARIS"
    detail["A1"].font = Font(name="Aptos Display", size=17, bold=True, color=WHITE)
    detail["A1"].fill = PatternFill("solid", fgColor=NAVY)
    detail["A1"].alignment = Alignment(vertical="center")
    detail.row_dimensions[1].height = 27
    detail.merge_cells("A3:X3")
    detail["A3"] = "Semua barang • Termasuk seluruh kepemilikan, kategori, dan status"
    detail["A3"].font = Font(name="Aptos", size=10, italic=True, color=SLATE)
    detail.row_dimensions[3].height = 23
    for index, width in enumerate(DETAIL_WIDTHS, start=1):
        detail.column_dimensions[get_column_letter(index)].width = width
    for column, header in enumerate(DETAIL_HEADERS, start=1):
        cell = detail.cell(5, column, header)
        cell.font = Font(name="Aptos", size=10, bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=VIOLET)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    detail.row_dimensions[5].height = 32

    ownership_counts = Counter()
    category_counts = Counter()
    condition_counts = Counter()
    status_counts = Counter()
    item_count = unit_count = assigned_count = maintenance_count = 0
    total_value = Decimal("0")
    items = InventoryItem.objects.select_related("assigned_to").order_by("asset_code", "pk")
    for item in items.iterator(chunk_size=500):
        item_count += 1
        unit_count += item.quantity
        total_value += item.total_value
        assigned_count += item.status == "assigned"
        maintenance_count += item.status == "maintenance"
        ownership_counts[item.get_ownership_display()] += 1
        category_counts[item.get_category_display()] += 1
        condition_label = item.get_condition_display() if item.category != "software" else ""
        if condition_label:
            condition_counts[condition_label] += 1
        status_counts[item.get_status_display()] += 1
        purchase_note = (
            "Tidak diketahui" if item.purchase_date_unknown
            else "Tercatat" if item.purchase_date else "Belum diisi"
        )
        member = item.assigned_to
        values = [
            safe_excel_text(item.asset_code), safe_excel_text(item.item_name),
            safe_excel_text(item.get_category_display()), safe_excel_text(item.brand),
            safe_excel_text(item.model), safe_excel_text(item.serial_number),
            safe_excel_text(item.specifications), item.purchase_date,
            item.received_date, purchase_note, safe_excel_text(item.get_ownership_display()),
            safe_excel_text(item.third_party_name), safe_excel_text(condition_label),
            safe_excel_text(item.get_status_display()), item.quantity,
            item.purchase_price, item.total_value,
            safe_excel_text(member.full_name if member else ""),
            safe_excel_text(member.division if member else ""),
            safe_excel_text(item.location if item.category != "software" else ""), item.warranty_expiry,
            safe_excel_text(item.notes), local_excel_datetime(item.created_at),
            local_excel_datetime(item.updated_at),
        ]
        detail.append(values)
        row = detail.max_row
        fill = PatternFill("solid", fgColor="FAF9FF" if item_count % 2 == 0 else WHITE)
        for cell in detail[row]:
            cell.fill = fill
            cell.font = Font(name="Aptos", size=10, color="0F172A")
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column in (2, 7, 22))
            cell.border = Border(bottom=Side(style="hair", color="E2E8F0"))
        for column in (8, 9, 21):
            detail.cell(row, column).number_format = DATE_FORMAT
        for column in (16, 17):
            detail.cell(row, column).number_format = CURRENCY_FORMAT
        for column in (23, 24):
            detail.cell(row, column).number_format = DATETIME_FORMAT
        detail.cell(row, 15).number_format = "#,##0"
        detail.row_dimensions[row].height = 21

    metrics = [
        ("JENIS BARANG", item_count, "0"),
        ("TOTAL UNIT", unit_count, "#,##0"),
        ("DIGUNAKAN", assigned_count, "0"),
        ("PERBAIKAN", maintenance_count, "0"),
        ("NILAI INVENTARIS", total_value, CURRENCY_FORMAT),
    ]
    for index, (label, value, number_format) in enumerate(metrics):
        first = index * 2 + 1
        last = 11 if index == 4 else first + 1
        first_letter, last_letter = get_column_letter(first), get_column_letter(last)
        summary.merge_cells(f"{first_letter}5:{last_letter}5")
        summary.merge_cells(f"{first_letter}6:{last_letter}7")
        heading = summary.cell(5, first, label)
        heading.font = Font(name="Aptos", size=9, bold=True, color=VIOLET)
        heading.fill = PatternFill("solid", fgColor=PALE)
        heading.alignment = Alignment(horizontal="center", vertical="center")
        number = summary.cell(6, first, value)
        number.font = Font(name="Aptos Display", size=17, bold=True, color=NAVY)
        number.fill = PatternFill("solid", fgColor=PALE)
        number.alignment = Alignment(horizontal="center", vertical="center")
        number.number_format = number_format
    summary.row_dimensions[5].height = 24
    summary.row_dimensions[6].height = 27
    summary.row_dimensions[7].height = 17

    breakdowns = [
        (1, "KEPEMILIKAN", ownership_counts),
        (4, "KATEGORI", category_counts),
        (7, "KONDISI", condition_counts),
        (10, "STATUS BARANG", status_counts),
    ]
    for first_column, title, counts in breakdowns:
        section_header(summary, first_column, title)
        for row, (label, count) in enumerate(sorted(counts.items()), start=12):
            summary.cell(row, first_column, label).font = Font(name="Aptos", size=10, color=SLATE)
            number = summary.cell(row, first_column + 1, count)
            number.font = Font(name="Aptos", size=10, bold=True, color=NAVY)
            number.alignment = Alignment(horizontal="right")
        summary.column_dimensions[get_column_letter(first_column)].width = (
            28 if first_column == 4 else 22
        )
    detail.freeze_panes = "D6"
    detail.auto_filter.ref = f"A5:X{max(detail.max_row, 6)}"
    detail.sheet_properties.pageSetUpPr.fitToPage = True
    detail.page_setup.orientation = "landscape"
    detail.page_setup.fitToWidth = 1
    detail.print_title_rows = "1:5"
    summary.sheet_properties.pageSetUpPr.fitToPage = True
    summary.page_setup.orientation = "landscape"
    summary.page_setup.fitToWidth = 1
    return workbook
