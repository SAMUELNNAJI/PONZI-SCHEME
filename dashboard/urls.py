"""
Dashboard app routes.

Pages are served at their exact filenames (/dashboard.html, /plans.html, ...)
because every internal link and asset reference in the HTML is a bare
relative filename. Clean aliases (/dashboard, /plans, ...) point at the
same views so hand-typed addresses work too.
"""
from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),

    # Public pages
    path('plans.html', views.plans, name='plans'),
    path('plans', views.plans, name='plans_clean'),

    # Account pages (login required)
    path('dashboard.html', views.dashboard, name='dashboard_page'),
    path('dashboard', views.dashboard, name='dashboard_clean'),
    path('deposit.html', views.deposit, name='deposit'),
    path('deposit', views.deposit, name='deposit_clean'),
    path('withdraw.html', views.withdraw, name='withdraw'),
    path('withdraw', views.withdraw, name='withdraw_clean'),
    path('history.html', views.history, name='history'),
    path('history', views.history, name='history_clean'),
    path('referrals.html', views.referrals, name='referrals'),
    path('referrals', views.referrals, name='referrals_clean'),
    path('settings.html', views.settings_view, name='settings'),
    path('settings', views.settings_view, name='settings_clean'),
]