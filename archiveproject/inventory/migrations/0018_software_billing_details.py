from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0017_separate_internet_sim_cards")]

    operations = [
        migrations.AddField(
            model_name="inventoryitem", name="software_billing_type",
            field=models.CharField(blank=True, choices=[("one_time", "Sekali bayar"), ("subscription", "Langganan")], max_length=20, verbose_name="Jenis biaya"),
        ),
        migrations.AddField(
            model_name="inventoryitem", name="software_billing_cycle",
            field=models.CharField(blank=True, choices=[("monthly", "Bulanan"), ("yearly", "Tahunan"), ("other", "Lainnya")], max_length=20, verbose_name="Periode langganan"),
        ),
        migrations.AddField(
            model_name="inventoryitem", name="software_payment_method",
            field=models.CharField(blank=True, max_length=120, verbose_name="Cara pembayaran"),
        ),
        migrations.AddField(
            model_name="inventoryitem", name="software_renewal_date",
            field=models.DateField(blank=True, null=True, verbose_name="Tanggal perpanjangan berikutnya"),
        ),
    ]
