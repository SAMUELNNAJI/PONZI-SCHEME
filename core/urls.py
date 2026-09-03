"""
Page routes.

Pages are served at their exact filenames (/dashboard.html, /plans.html, ...)
because every internal link and asset reference in the HTML is a bare
relative filename. Clean aliases (/dashboard, /plans, ...) redirect to the
canonical URLs so hand-typed addresses work too.
"""
from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path('', views.index, name='index'),

    # Canonical (filename) routes
    path('dashboard.html', views.dashboard, name='dashboard'),
    path('plans.html', views.plans, name='plans'),
    path('deposit.html', views.deposit, name='deposit'),
    path('withdraw.html', views.withdraw, name='withdraw'),
    path('history.html', views.history, name='history'),
    path('referrals.html', views.referrals, name='referrals'),
    path('settings.html', views.settings_view, name='settings'),
    path('login.html', views.login_view, name='login'),
    path('signup.html', views.signup_view, name='signup'),

    # Clean aliases -> canonical
    path('dashboard', RedirectView.as_view(url='/dashboard.html', permanent=False)),
    path('plans', RedirectView.as_view(url='/plans.html', permanent=False)),
    path('deposit', RedirectView.as_view(url='/deposit.html', permanent=False)),
    path('withdraw', RedirectView.as_view(url='/withdraw.html', permanent=False)),
    path('history', RedirectView.as_view(url='/history.html', permanent=False)),
    path('referrals', RedirectView.as_view(url='/referrals.html', permanent=False)),
    path('settings', RedirectView.as_view(url='/settings.html', permanent=False)),
    path('login', RedirectView.as_view(url='/login.html', permanent=False)),
    path('signup', RedirectView.as_view(url='/signup.html', permanent=False)),
]