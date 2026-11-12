from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0009_riskcause_identification")]

    operations = [
        migrations.AlterField(model_name="riskregister", name="inherent_likelihood", field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Kemungkinan inheren")),
        migrations.AlterField(model_name="riskregister", name="inherent_impact", field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Dampak inheren")),
        migrations.AlterField(model_name="riskregister", name="residual_likelihood", field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Kemungkinan residual")),
        migrations.AlterField(model_name="riskregister", name="residual_impact", field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Dampak residual")),
    ]
