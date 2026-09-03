"""
Authentication routes.

Both the filename URL and the clean alias point at the same view so the
form posts correctly no matter which address the visitor is on.
"""
from django.urls import path

from . import views

app_name = 'authentication'

urlpatterns = [
    path('login.html', views.login_view, name='login_page'),
    path('login', views.login_view, name='login'),
    path('signup.html', views.signup_view, name='signup_page'),
    path('signup', views.signup_view, name='signup'),
    path('logout', views.logout_view, name='logout'),
]