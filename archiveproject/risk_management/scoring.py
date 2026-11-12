"""Risk levels from the approved likelihood-by-impact matrix."""

from django.db.models import Case, IntegerField, Q, Value, When


# Rows are impact 1..5; columns are likelihood 1..5.
MATRIX_COLORS = (
    ("blue", "blue", "green", "green", "yellow"),
    ("blue", "green", "yellow", "yellow", "orange"),
    ("green", "yellow", "yellow", "orange", "orange"),
    ("yellow", "yellow", "orange", "orange", "red"),
    ("orange", "orange", "orange", "red", "red"),
)
LEVEL_BY_COLOR = {
    "blue": "Sangat Rendah", "green": "Rendah", "yellow": "Sedang",
    "orange": "Tinggi", "red": "Sangat Tinggi",
}
LEVEL_ORDER = tuple(LEVEL_BY_COLOR.values())


def level_for(likelihood, impact):
    if not (1 <= likelihood <= 5 and 1 <= impact <= 5):
        raise ValueError("Kemungkinan dan dampak harus bernilai 1 sampai 5.")
    return LEVEL_BY_COLOR[MATRIX_COLORS[impact - 1][likelihood - 1]]


def level_filter(level, likelihood_field, impact_field):
    condition = Q(pk__in=[])
    for impact, row in enumerate(MATRIX_COLORS, 1):
        for likelihood, color in enumerate(row, 1):
            if LEVEL_BY_COLOR[color] == level:
                condition |= Q(**{likelihood_field: likelihood, impact_field: impact})
    return condition


def level_rank(likelihood_field, impact_field):
    return Case(
        *(When(level_filter(level, likelihood_field, impact_field), then=Value(rank))
          for rank, level in enumerate(LEVEL_ORDER, 1)),
        default=Value(0), output_field=IntegerField(),
    )
