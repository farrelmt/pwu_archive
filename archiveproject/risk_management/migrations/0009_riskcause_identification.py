from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0008_riskcause")]

    operations = [
        migrations.AddField(model_name="riskcause", name="impact", field=models.TextField(blank=True, verbose_name="Dampak")),
        migrations.AddField(model_name="riskcause", name="inherent_likelihood", field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Kemungkinan inheren")),
        migrations.AddField(model_name="riskcause", name="inherent_impact", field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Dampak inheren")),
        migrations.AddField(model_name="riskcause", name="identification_notes", field=models.TextField(blank=True, verbose_name="Keterangan identifikasi")),
    ]
