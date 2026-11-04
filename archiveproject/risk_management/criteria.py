"""Read the approved impact criteria directly from the report template."""
from functools import lru_cache

from openpyxl import load_workbook

from .exports import TEMPLATE


IMPACT_HEADERS = (
    "Keuangan", "Pemasaran", "Operasional", "Sasaran Perusahaan",
    "Citra Perusahaan", "Hukum", "Lingkungan", "K3",
)


@lru_cache(maxsize=1)
def impact_criteria():
    workbook = load_workbook(TEMPLATE, read_only=True, data_only=True)
    try:
        return tuple({"level": values[0], "criteria": tuple(values[1:])}
                     for values in workbook["NEW Kriteria Dampak"].iter_rows(
                         min_row=8, max_row=12, min_col=1, max_col=9, values_only=True,
                     ))
    finally:
        workbook.close()
