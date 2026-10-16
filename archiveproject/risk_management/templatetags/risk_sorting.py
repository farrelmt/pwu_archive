from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag(takes_context=True)
def sort_header(context, field, label):
    if not context.get("sorting_enabled"):
        return label
    active = context.get("sort_key") == field
    descending = context.get("sort_order") == "desc"
    params = context["request"].GET.copy()
    params.pop("page", None)
    params["sort"] = field
    params["order"] = "desc" if active and not descending else "asc"
    indicator = ("▼" if descending else "▲") if active else "↕"
    return format_html(
        '<a href="?{}" class="inline-flex items-center gap-1 hover:text-blue-700" '
        'aria-label="Urutkan {} {}">{} <span aria-hidden="true">{}</span></a>',
        params.urlencode(), label, "menurun" if params["order"] == "desc" else "menaik",
        label, indicator,
    )
