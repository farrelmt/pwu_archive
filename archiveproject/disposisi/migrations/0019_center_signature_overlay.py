from django.db import migrations


OLD_VALUE = 'preserveAspectRatio="xMinYMin meet"'
NEW_VALUE = 'preserveAspectRatio="xMidYMin meet"'


def center_existing_signature_overlays(apps, schema_editor):
    Disposisi = apps.get_model('disposisi', 'Disposisi')
    for disposisi in Disposisi.objects.filter(
        isi_disposisi__contains=OLD_VALUE
    ).iterator():
        disposisi.isi_disposisi = disposisi.isi_disposisi.replace(
            OLD_VALUE, NEW_VALUE
        )
        disposisi.save(update_fields=['isi_disposisi'])


def restore_left_aligned_signature_overlays(apps, schema_editor):
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
        ('disposisi', '0018_normalize_signature_aspect_ratio'),
    ]

    operations = [
        migrations.RunPython(
            center_existing_signature_overlays,
            restore_left_aligned_signature_overlays,
        ),
    ]
