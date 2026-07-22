
from django import template

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    if user.is_superuser:
        return True # Superusers can see everything
    return user.groups.filter(name=group_name).exists()


@register.filter(name='can_edit_disposisi')
def can_edit_disposisi(user):
    return user.is_authenticated and user.can_edit_disposisi
