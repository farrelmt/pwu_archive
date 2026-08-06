from django.db import migrations


OLD_VALUE = 'preserveAspectRatio="xMidYMin meet"'
NEW_VALUE = 'preserveAspectRatio="xMidYMax meet"'


def anchor_existing_signatures_to_bottom(apps, schema_editor):
    Disposisi = apps.get_model('disposisi', 'Disposisi')
    for disposisi in Disposisi.objects.filter(
        isi_disposisi__contains=OLD_VALUE
    ).iterator():
        disposisi.isi_disposisi = disposisi.isi_disposisi.replace(
            OLD_VALUE, NEW_VALUE
        )
        disposisi.save(update_fields=['isi_disposisi'])


def restore_top_anchored_signatures(apps, schema_editor):
    Disposisi = apps.get_model('disposisi', 'Disposisi')
    for disposisi in Disposisi.objects.filter(
        isi_disposisi__contains=NEW_VALUE
    ).iterator():
        disposisi.isi_disposisi = disposisi.isi_disposisi.replace(
            NEW_VALUE, OLD_VALUE
        )
        disposisi.save(update_fields=['isi_disposisi'])


class Migration(migrations.Migration):

    dependencies = [
        ('disposisi', '0019_center_signature_overlay'),
    ]

    operations = [
        migrations.RunPython(
            anchor_existing_signatures_to_bottom,
            restore_top_anchored_signatures,
        ),
    ]
