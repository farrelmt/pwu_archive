import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


def seed_wira_jatim_cooperative(apps, schema_editor):
    Company = apps.get_model('koperasi', 'Company')
    KoperasiAccess = apps.get_model('koperasi', 'KoperasiAccess')
    SystemUser = apps.get_model('accounts', 'SystemUser')

    Company.objects.get_or_create(
        code='PWU',
        defaults={
            'name': 'PT Panca Wira Usaha Jawa Timur',
            'company_type': 'holding',
            'is_active': True,
        },
    )
    accountant = SystemUser.objects.filter(username='akuntan').first()
    if accountant:
        access, _created = KoperasiAccess.objects.get_or_create(
            user=accountant,
            company=None,
            defaults={'role': 'treasurer', 'is_active': True},
        )
        if access.role in {'finance', 'officer'} or not access.is_active:
            access.role = 'treasurer'
            access.is_active = True
            access.save(update_fields=['role', 'is_active'])


class Migration(migrations.Migration):

    dependencies = [
        ('koperasi', '0002_remove_koperasiaccess_unique_koperasi_user_company_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='cashtransaction',
            name='account',
            field=models.CharField(choices=[('cash', 'Kas'), ('bank', 'Bank')], default='cash', max_length=10, verbose_name='Kas/Bank'),
        ),
        migrations.AddField(
            model_name='cashtransaction',
            name='counterparty',
            field=models.CharField(blank=True, max_length=200, verbose_name='Diterima dari/Dibayar kepada'),
        ),
        migrations.AddField(
            model_name='cashtransaction',
            name='unit',
            field=models.CharField(choices=[('savings_loan', 'Sie Simpan Pinjam'), ('business', 'Sie Usaha'), ('general', 'Koperasi Umum')], default='savings_loan', max_length=20, verbose_name='Unit koperasi'),
        ),
        migrations.AddField(
            model_name='loan',
            name='chairman_approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='loan',
            name='chairman_approved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='chairman_approved_koperasi_loans', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='loan',
            name='payment_due_day',
            field=models.PositiveSmallIntegerField(default=10, verbose_name='Tanggal jatuh tempo bulanan'),
        ),
        migrations.AddField(
            model_name='loan',
            name='payment_method',
            field=models.CharField(choices=[('cash', 'Tunai'), ('transfer', 'Transfer'), ('payroll', 'Potong gaji (autodebet payroll)'), ('meal_allowance', 'Potong uang makan tanggal 10')], default='payroll', max_length=20, verbose_name='Metode pembayaran'),
        ),
        migrations.AddField(
            model_name='loan',
            name='savings_treasurer_approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='loan',
            name='savings_treasurer_approved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='treasurer_approved_koperasi_loans', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='member',
            name='approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='member',
            name='approved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_koperasi_members', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='member',
            name='exit_date',
            field=models.DateField(blank=True, null=True, verbose_name='Tanggal keluar'),
        ),
        migrations.AlterField(
            model_name='koperasiaccess',
            name='role',
            field=models.CharField(choices=[('chairman', 'Ketua Koperasi'), ('treasurer', 'Bendahara'), ('savings_treasurer', 'Bendahara Sie Simpan Pinjam'), ('business_treasurer', 'Bendahara Sie Usaha'), ('member_section', 'Sie Anggota'), ('supervisor', 'Pengawas'), ('admin', 'Administrator Koperasi'), ('manager', 'Manajer Koperasi'), ('finance', 'Keuangan'), ('officer', 'Petugas'), ('auditor', 'Auditor'), ('viewer', 'Pembaca')], max_length=20),
        ),
        migrations.AlterField(
            model_name='member',
            name='status',
            field=models.CharField(choices=[('pending', 'Menunggu Persetujuan'), ('active', 'Aktif'), ('inactive', 'Tidak Aktif'), ('resigned', 'Keluar'), ('rejected', 'Ditolak')], default='active', max_length=20),
        ),
        migrations.CreateModel(
            name='BusinessTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_number', models.CharField(max_length=40, unique=True, verbose_name='Nomor transaksi')),
                ('transaction_date', models.DateField(verbose_name='Tanggal')),
                ('activity_type', models.CharField(choices=[('rice_purchase', 'Pembelian beras anggota'), ('office_procurement', 'Pengadaan barang kantor'), ('member_financing', 'Pembiayaan barang anggota'), ('other', 'Usaha lainnya')], max_length=30, verbose_name='Kegiatan')),
                ('direction', models.CharField(choices=[('income', 'Pendapatan'), ('expense', 'Pembelian/Beban')], max_length=10, verbose_name='Jenis pencatatan')),
                ('description', models.TextField(verbose_name='Barang/Keterangan')),
                ('quantity', models.DecimalField(decimal_places=2, default=1, max_digits=12, verbose_name='Jumlah')),
                ('unit', models.CharField(default='unit', max_length=30, verbose_name='Satuan')),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=15, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='Harga satuan')),
                ('payment_method', models.CharField(choices=[('cash', 'Tunai'), ('transfer', 'Transfer'), ('payroll', 'Potong gaji (autodebet payroll)'), ('meal_allowance', 'Potong uang makan tanggal 10')], default='payroll', max_length=20, verbose_name='Metode pembayaran')),
                ('status', models.CharField(choices=[('submitted', 'Diajukan'), ('approved', 'Disetujui'), ('rejected', 'Ditolak'), ('completed', 'Selesai')], default='submitted', max_length=15)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, verbose_name='Catatan')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_business_transactions', to=settings.AUTH_USER_MODEL)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='business_transactions', to='koperasi.company')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_business_transactions', to=settings.AUTH_USER_MODEL)),
                ('member', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='business_transactions', to='koperasi.member')),
            ],
            options={
                'verbose_name': 'Transaksi Sie Usaha',
                'verbose_name_plural': 'Transaksi Sie Usaha',
                'ordering': ['-transaction_date', '-pk'],
            },
        ),
        migrations.CreateModel(
            name='PayrollDeduction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('period', models.DateField(help_text='Gunakan tanggal pertama pada bulan potongan.', verbose_name='Periode')),
                ('principal_saving', models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='Simpanan pokok')),
                ('mandatory_saving', models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='Simpanan wajib')),
                ('voluntary_saving', models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='Simpanan sukarela')),
                ('loan_principal', models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='Angsuran pokok pinjaman')),
                ('loan_interest', models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='Bunga pinjaman')),
                ('business_deduction', models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='Potongan Sie Usaha')),
                ('notes', models.TextField(blank=True, verbose_name='Catatan')),
                ('status', models.CharField(choices=[('draft', 'Draf'), ('posted', 'Dibukukan')], default='draft', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_payroll_deductions', to=settings.AUTH_USER_MODEL)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payroll_deductions', to='koperasi.member')),
            ],
            options={
                'verbose_name': 'Potongan payroll',
                'verbose_name_plural': 'Potongan payroll',
                'ordering': ['-period', 'member__full_name'],
                'constraints': [models.UniqueConstraint(fields=('member', 'period'), name='unique_member_payroll_period')],
            },
        ),
        migrations.RunPython(
            seed_wira_jatim_cooperative,
            migrations.RunPython.noop,
        ),
    ]
