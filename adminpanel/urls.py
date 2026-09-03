from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'adminpanel'

urlpatterns = [
    path('', RedirectView.as_view(url='/adminpanel/users', permanent=False)),
    path('users', views.users, name='users'),
    path('plans', views.plans, name='plans'),
    path('plans/add', views.plan_form, name='plan_add'),
    path('plans/<int:pk>/edit', views.plan_form, name='plan_edit'),
    path('deposits', views.deposits, name='deposits'),
    path('withdrawals', views.withdrawals, name='withdrawals'),
    path('transactions', views.transactions, name='transactions'),
    path('notify', views.notify, name='notify'),
    path('settings', views.settings_view, name='settings'),
    path('logs', views.logs, name='logs'),
]