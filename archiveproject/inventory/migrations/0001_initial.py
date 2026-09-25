import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations, models


def seed_inventory_users(apps, schema_editor):
    User = apps.get_model("accounts", "SystemUser")
    Access = apps.get_model("inventory", "InventoryAccess")
    users = [
        ("inventory_manager", "Manajer", "Inventaris", "manager"),
        ("inventory_officer", "Petugas", "Inventaris", "officer"),
        ("inventory_viewer", "Pembaca", "Inventaris", "viewer"),
    ]
    for username, first_name, last_name, role in users:
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"role": "inventory", "email": "it.pwujatim@gmail.com"},
        )
        user.role = "inventory"
        user.first_name = first_name
        user.last_name = last_name
        user.email = user.email or "it.pwujatim@gmail.com"
        user.is_active = True
        user.password = make_password(username)
        user.save()
        Access.objects.update_or_create(user=user, defaults={"role": role, "is_active": True})


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0012_add_inventory_user_role"),
    ]
    operations = [
        migrations.CreateModel(
            name="CompanyMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employee_id", models.CharField(max_length=50, unique=True, verbose_name="NIP/NIK")),
                ("full_name", models.CharField(max_length=180, verbose_name="Nama lengkap")),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=30, verbose_name="Nomor telepon")),
                ("division", models.CharField(max_length=120, verbose_name="Divisi")),
                ("position", models.CharField(max_length=120, verbose_name="Jabatan")),
                ("join_date", models.DateField(blank=True, null=True, verbose_name="Tanggal bergabung")),
                ("status", models.CharField(choices=[("active", "Aktif"), ("inactive", "Tidak Aktif"), ("resigned", "Keluar")], default="active", max_length=20)),
                ("notes", models.TextField(blank=True, verbose_name="Catatan")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Anggota perusahaan", "verbose_name_plural": "Anggota perusahaan", "ordering": ["full_name"]},
        ),
        migrations.CreateModel(
            name="InventoryAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("manager", "Manajer Inventaris"), ("officer", "Petugas Inventaris"), ("viewer", "Pembaca Inventaris")], max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="inventory_access", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Hak akses inventaris", "verbose_name_plural": "Hak akses inventaris"},
        ),
        migrations.CreateModel(
            name="InventoryItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("asset_code", models.CharField(max_length=50, unique=True, verbose_name="Kode aset")),
                ("item_name", models.CharField(max_length=180, verbose_name="Nama barang")),
                ("category", models.CharField(choices=[("hardware", "Perangkat Keras"), ("software", "Perangkat Lunak"), ("furniture", "Furnitur"), ("vehicle", "Kendaraan"), ("tool", "Peralatan Kerja"), ("office", "Perlengkapan Kantor"), ("other", "Lainnya")], max_length=20, verbose_name="Kategori")),
                ("brand", models.CharField(blank=True, max_length=100, verbose_name="Merek")),
                ("model", models.CharField(blank=True, max_length=120, verbose_name="Model/Tipe")),
                ("serial_number", models.CharField(blank=True, db_index=True, max_length=120, verbose_name="Nomor seri")),
                ("specifications", models.TextField(blank=True, verbose_name="Spesifikasi")),
                ("received_date", models.DateField(verbose_name="Tanggal diterima")),
                ("purchase_price", models.DecimalField(decimal_places=2, default=0, max_digits=16, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Harga satuan")),
                ("quantity", models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)], verbose_name="Jumlah")),
                ("condition", models.CharField(choices=[("new", "Baru"), ("good", "Baik"), ("fair", "Cukup"), ("damaged", "Rusak")], default="good", max_length=20, verbose_name="Kondisi")),
                ("status", models.CharField(choices=[("stock", "Tersedia"), ("assigned", "Digunakan"), ("maintenance", "Perbaikan"), ("retired", "Tidak Digunakan"), ("lost", "Hilang")], default="stock", max_length=20)),
                ("location", models.CharField(blank=True, max_length=160, verbose_name="Lokasi")),
                ("warranty_expiry", models.DateField(blank=True, null=True, verbose_name="Garansi berakhir")),
                ("notes", models.TextField(blank=True, verbose_name="Catatan")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inventory_items", to="inventory.companymember", verbose_name="Pengguna/Penanggung jawab")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_inventory_items", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="updated_inventory_items", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Barang inventaris", "verbose_name_plural": "Barang inventaris", "ordering": ["item_name", "asset_code"]},
        ),
        migrations.CreateModel(
            name="InventoryActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=40)),
                ("description", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activities", to="inventory.inventoryitem")),
            ],
            options={"verbose_name_plural": "Aktivitas inventaris", "ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="companymember", index=models.Index(fields=["division", "status"], name="inv_member_div_status_idx")),
        migrations.AddIndex(model_name="inventoryitem", index=models.Index(fields=["category", "status"], name="inv_item_cat_status_idx")),
        migrations.AddIndex(model_name="inventoryitem", index=models.Index(fields=["assigned_to", "status"], name="inv_item_owner_status_idx")),
        migrations.RunPython(seed_inventory_users, migrations.RunPython.noop),
    ]
