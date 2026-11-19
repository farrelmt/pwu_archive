from django.urls import path, register_converter

from . import views
from .converters import EncryptedRiskIdConverter

register_converter(EncryptedRiskIdConverter, "riskid")

app_name = "risk"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("activity-log/", views.activity_log, name="activity_log"),
    path("risiko/", views.risk_list, name="risk_list"),
    path("laporan-tahunan/", views.annual_report, name="annual_report"),
    path("risiko/impor-workbook/", views.workbook_import, name="workbook_import"),
    path("risiko/template-impor/", views.workbook_import_template, name="workbook_import_template"),
    path("risiko/tambah/", views.risk_create, name="risk_create"),
    path("risiko/<riskid:pk>/", views.risk_detail, name="risk_detail"),
    path("risiko/<riskid:pk>/edit/", views.risk_edit, name="risk_edit"),
    path("risiko/<riskid:pk>/hapus/", views.risk_delete, name="risk_delete"),
    path("risiko/<riskid:risk_pk>/pemantauan/tambah/", views.monitoring_create, name="monitoring_create"),
    path("pemantauan/<int:pk>/edit/", views.monitoring_edit, name="monitoring_edit"),
    path("pemantauan/<int:monitoring_pk>/aksi/tambah/", views.action_create, name="action_create"),
    path("aksi/<int:pk>/edit/", views.action_edit, name="action_edit"),
    path("pemantauan/", views.monitoring_report, name="monitoring_report"),
    path("pedoman-penilaian/", views.scoring_guide, name="scoring_guide"),
    path("kriteria-risiko/", views.scoring_guide, name="criteria"),
    path("perlakuan-risiko/tambah/", views.treatment_create, name="treatment_create"),
    path("perlakuan-risiko/risiko/<riskid:risk_pk>/tambah/", views.treatment_create, name="treatment_create_for_risk"),
    path("perlakuan-risiko/<int:pk>/edit/", views.treatment_edit, name="treatment_edit"),
    path("divisi/", views.divisions, name="divisions"),
    path("divisi/<int:pk>/pic/", views.division_pic_edit, name="division_pic_edit"),
]
