from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Profile


def _safe_redirect(request):
    """Redirect to `next` if it is a safe local URL, else the dashboard."""
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        return redirect(next_url)
    return redirect('dashboard:dashboard_page')


def login_view(request):
    """Sign in with email + password."""
    error = None
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return _safe_redirect(request)
        error = 'Invalid email or password.'
    return render(request, 'login.html', {'error': error})


def signup_view(request):
    """Create a new account and sign the user in."""
    error = None
    if request.method == 'POST':
        firstname = request.POST.get('firstname', '').strip()
        lastname = request.POST.get('lastname', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm', '')

        if not (firstname and lastname and email and password):
            error = 'Please fill in all required fields.'
        elif password != confirm:
            error = 'Passwords do not match.'
        else:
            try:
                validate_password(password)
                User = get_user_model()
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=firstname,
                    last_name=lastname,
                )
                Profile.objects.create(user=user, phone=phone)
                login(request, user)
                return _safe_redirect(request)
            except ValidationError as exc:
                error = ' '.join(exc.messages)
            except IntegrityError:
                error = 'An account with this email already exists. Try signing in.'
    return render(request, 'signup.html', {'error': error})


def logout_view(request):
    """Log the user out and return to the landing page."""
    logout(request)
    return redirect('dashboard:index')
