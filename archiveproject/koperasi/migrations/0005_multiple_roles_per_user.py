from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("koperasi", "0004_add_secretary_and_seed_organization_users"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="koperasiaccess",
            name="unique_koperasi_user_company",
        ),
        migrations.AddConstraint(
            model_name="koperasiaccess",
            constraint=models.UniqueConstraint(
                fields=("user", "company", "role"),
                name="unique_koperasi_user_company_role",
                nulls_distinct=False,
            ),
        ),
    ]
