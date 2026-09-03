from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Profile


def _safe_redirect(request):
    """Redirect to `next` if it is a safe local URL, else to an appropriate home."""
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        return redirect(next_url)
    if request.user.is_staff:
        return redirect('/adminpanel/')
    return redirect('dashboard:dashboard_page')


def login_view(request):
    """Sign in with username or email + password."""
    error = None
    if request.method == 'POST':
        identifier = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        # 1) Try the input directly as a username.
        user = authenticate(request, username=identifier, password=password)

        # 2) Fall back to a case-insensitive email lookup (e.g. superusers
        #    created via createsuperuser have a username different from email).
        if user is None:
            User = get_user_model()
            email_user = User.objects.filter(email__iexact=identifier).first()
            if email_user is not None:
                user = authenticate(
                    request,
                    username=email_user.username,
                    password=password,
                )

        if user is not None:
            login(request, user)
            return _safe_redirect(request)
        error = 'Invalid email or password.'
    return render(request, 'authentication/login.html', {'error': error})


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
    return render(request, 'authentication/signup.html', {'error': error})


def logout_view(request):
    """Log the user out and return to the landing page."""
    logout(request)
    return redirect('dashboard:index')
