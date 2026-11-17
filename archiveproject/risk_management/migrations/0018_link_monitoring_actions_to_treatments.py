from django.db import migrations, models
import django.db.models.deletion


def link_matching_actions(apps, schema_editor):
    Treatment = apps.get_model("risk_management", "RiskTreatment")
    Monitoring = apps.get_model("risk_management", "RiskMonitoring")
    Action = apps.get_model("risk_management", "RiskActionPlan")
    database = schema_editor.connection.alias

    for monitoring in Monitoring.objects.using(database).all().iterator():
        actions = list(Action.objects.using(database).filter(monitoring_id=monitoring.pk).order_by("pk"))
        for treatment in Treatment.objects.using(database).filter(risk_id=monitoring.risk_id).order_by("pk"):
            action = next((item for item in actions if item.treatment_id is None
                           and item.description.strip() == treatment.action_plan.strip()), None)
            if action is not None:
                Action.objects.using(database).filter(pk=action.pk).update(treatment_id=treatment.pk)
                action.treatment_id = treatment.pk


class Migration(migrations.Migration):
    dependencies = [("risk_management", "0017_division_wide_risk_sequence")]

    operations = [
        migrations.AddField(
            model_name="riskactionplan",
            name="treatment",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="monitoring_actions", to="risk_management.risktreatment",
            ),
        ),
        migrations.RunPython(link_matching_actions, migrations.RunPython.noop),
    ]
