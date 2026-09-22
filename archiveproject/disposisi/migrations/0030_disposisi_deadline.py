from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('disposisi', '0029_rename_kepala_spi'),
    ]

    operations = [
        migrations.AddField(
            model_name='disposisi',
            name='deadline',
            field=models.DateField(blank=True, null=True),
        ),
    ]
