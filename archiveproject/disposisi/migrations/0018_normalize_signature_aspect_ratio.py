from django.db import migrations


OLD_VALUE = 'preserveAspectRatio="none"'
NEW_VALUE = 'preserveAspectRatio="xMinYMin meet"'


def preserve_existing_signature_aspect_ratio(apps, schema_editor):
    Disposisi = apps.get_model('disposisi', 'Disposisi')
    for disposisi in Disposisi.objects.filter(
        isi_disposisi__contains=OLD_VALUE
    ).iterator():
        disposisi.isi_disposisi = disposisi.isi_disposisi.replace(
            OLD_VALUE, NEW_VALUE
        )
        disposisi.save(update_fields=['isi_disposisi'])


def restore_stretched_signature_aspect_ratio(apps, schema_editor):
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
        ('disposisi', '0017_disposisi_isi_disposisi'),
    ]

    operations = [
        migrations.RunPython(
            preserve_existing_signature_aspect_ratio,
            restore_stretched_signature_aspect_ratio,
        ),
    ]
