from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font

from accounts.models import SystemUser


HEADERS = (
    'ID', 'Username', 'First name', 'Last name', 'Email', 'Phone',
    'Role', 'Active', 'Staff', 'Superuser', 'Joined', 'Last login',
)


def safe_cell(value):
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
        return "'" + value
    return value


def local_datetime(value):
    if value is None:
        return ''
    return timezone.localtime(value).strftime('%Y-%m-%d %H:%M:%S')


class Command(BaseCommand):
    help = 'Export all PWU user accounts to an Excel file without password hashes.'

    def add_arguments(self, parser):
        parser.add_argument('--output', default='/tmp/pwu_users.xlsx')

    def handle(self, *args, **options):
        output = Path(options['output']).expanduser()
        if output.suffix.lower() != '.xlsx':
            raise ValueError('Output file must have an .xlsx extension')
        output.parent.mkdir(parents=True, exist_ok=True)

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Users'
        sheet.append(HEADERS)
        for cell in sheet[1]:
            cell.font = Font(bold=True)

        count = 0
        for user in SystemUser.objects.order_by('id').iterator():
            sheet.append((
                user.pk, safe_cell(user.username), safe_cell(user.first_name),
                safe_cell(user.last_name), safe_cell(user.email), safe_cell(user.phone or ''),
                safe_cell(user.get_role_display()), user.is_active, user.is_staff,
                user.is_superuser, local_datetime(user.date_joined),
                local_datetime(user.last_login),
            ))
            count += 1

        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for column, width in {'A': 10, 'B': 24, 'C': 22, 'D': 22, 'E': 32,
                              'F': 20, 'G': 30, 'H': 12, 'I': 12, 'J': 14,
                              'K': 22, 'L': 22}.items():
            sheet.column_dimensions[column].width = width
        workbook.save(output)
        self.stdout.write(self.style.SUCCESS(f'Exported {count} users to {output}'))
