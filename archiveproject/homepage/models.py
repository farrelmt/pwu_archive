from django.db import models

class AppSetting(models.Model):
    report_email = models.EmailField()

    def __str__(self):
        return self.report_email
