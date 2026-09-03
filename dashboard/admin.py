from django.contrib import admin

from .models import Deposit, Notification, Plan, Transaction, Withdrawal

admin.site.register(Plan)
admin.site.register(Deposit)
admin.site.register(Withdrawal)
admin.site.register(Transaction)
admin.site.register(Notification)
