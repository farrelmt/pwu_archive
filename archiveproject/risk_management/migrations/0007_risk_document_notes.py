from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0006_workbook_template_fields")]
    operations = [
        migrations.AddField(model_name="riskregister", name="identification_notes", field=models.TextField("Keterangan identifikasi", blank=True)),
        migrations.AddField(model_name="riskregister", name="evaluation_notes", field=models.TextField("Keterangan analisis dan evaluasi", blank=True)),
    ]
