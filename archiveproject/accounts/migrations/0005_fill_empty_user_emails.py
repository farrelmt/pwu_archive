from django.db import migrations
from django.db.models import Q


PLACEHOLDER_EMAIL = 'it.pwujatim@gmail.com'


def fill_empty_user_emails(apps, schema_editor):
    system_user = apps.get_model('accounts', 'SystemUser')
    system_user.objects.filter(
        Q(email__isnull=True) | Q(email=''),
    ).update(email=PLACEHOLDER_EMAIL)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_activitylog'),
    ]

    operations = [
        migrations.RunPython(
            fill_empty_user_emails,
            migrations.RunPython.noop,
        ),
    ]
