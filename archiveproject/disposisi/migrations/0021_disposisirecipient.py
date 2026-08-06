from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('disposisi', '0020_anchor_signature_to_bottom'),
    ]

    operations = [
        migrations.CreateModel(
            name='DisposisiRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(
                    choices=[
                        ('direktur_utama', 'Direktur Utama'),
                        ('direktur_umum', 'Direktur Umum'),
                        ('kadiv_akuntansi', 'Kepala Divisi Akuntansi'),
                        ('kadiv_keuangan', 'Kepala Divisi Keuangan'),
                        ('kadiv_risiko', 'Kepala Divisi Manajemen Risiko'),
                        ('kadiv_legal_umum', 'Kepala Divisi Legal dan Umum'),
                        ('kadiv_aset', 'Kepala Divisi Aset'),
                        ('kadiv_spi', 'Kepala Divisi SPI'),
                    ],
                    max_length=30,
                )),
                ('disposisi', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='shared_recipients',
                    to='disposisi.disposisi',
                )),
            ],
            options={
                'ordering': ['role'],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('disposisi', 'role'),
                        name='unique_disposisi_recipient_role',
                    ),
                ],
            },
        ),
    ]
