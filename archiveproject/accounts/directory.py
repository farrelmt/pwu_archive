MEMBER_DIVISION_ORDER = (
    "Direksi",
    "Divisi Akuntansi",
    "Divisi Aset",
    "Divisi Keuangan",
    "Divisi Legal dan Umum",
    "Divisi Manajemen Risiko",
    "Divisi Sekretaris",
    "Divisi Satuan Pengawas Internal",
    "Divisi Umum",
    "Humas",
    "HRD",
    "Wirajatim KSO",
    "Divisi Umum & Legal",
    "Lainnya",
)


def member_division(user):
    """Return a member's chosen division, or infer it for older accounts."""
    if not isinstance(user, str):
        if user.division:
            return user.division
        user = user.username
    username = user
    username = (username or "").casefold()
    prefix_groups = (
        (("akuntansi_",), "Divisi Akuntansi"),
        (("aset_",), "Divisi Aset"),
        (("keuangan_",), "Divisi Keuangan"),
        (("legal_", "legal_umum_"), "Divisi Legal dan Umum"),
        (("manajemen_risiko_",), "Divisi Manajemen Risiko"),
        (("sekretaris_",), "Divisi Sekretaris"),
        (("spi_",), "Divisi Satuan Pengawas Internal"),
        (("umum_",), "Divisi Umum"),
        (("humas_",), "Humas"),
        (("hrd_",), "HRD"),
        (("wirajatim_kso_", "kso_"), "Wirajatim KSO"),
    )
    if username in {"direktur", "direktur_utama"}:
        return "Direksi"
    if username in {"it_pwu", "farrel_mt"}:
        return "Divisi Umum & Legal"
    for prefixes, division_name in prefix_groups:
        if username.startswith(prefixes):
            return division_name
    return "Lainnya"
