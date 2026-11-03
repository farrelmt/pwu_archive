from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0025_remove_cross_system_account_roles")]

    operations = [
        migrations.AddField(
            model_name="systemuser",
            name="job_description",
            field=models.TextField(blank=True, max_length=1000, verbose_name="Deskripsi pekerjaan"),
        ),
    ]
