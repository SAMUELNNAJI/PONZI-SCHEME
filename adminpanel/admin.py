from django.contrib import admin

from .models import ActivityLog, SiteSetting

admin.site.register(SiteSetting)
admin.site.register(ActivityLog)
