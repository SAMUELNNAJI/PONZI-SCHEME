from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Profile


def _full_url(path):
    from django.conf import settings
    return settings.SITE_BASE_URL.rstrip('/') + path


def _safe_redirect(request):
    """Redirect to `next` if it is a safe local URL, else to an appropriate home."""
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        return redirect(next_url)
    if request.user.is_staff:
        return redirect('adminpanel:users')
    return redirect('dashboard:dashboard_page')


def login_view(request):
    """Sign in with username or email + password."""
    error = None
    if request.method == 'POST':
        identifier = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        User = get_user_model()

        # 1) Try the input directly as a username.
        user = authenticate(request, username=identifier, password=password)

        # 2) Fall back to a case-insensitive email lookup.
        if user is None:
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
    """Create a new account, track referral, send welcome email, sign the user in."""
    error = None
    if request.method == 'POST':
        firstname = request.POST.get('firstname', '').strip()
        lastname = request.POST.get('lastname', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm', '')
        ref_code = request.POST.get('ref_code') or request.session.get('ref_code', '')

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
                profile = Profile.objects.create(user=user, phone=phone)
                # Track referral: only accept a valid, non-self code
                if ref_code and ref_code != profile.referral_code:
                    try:
                        referrer_profile = Profile.objects.get(referral_code=ref_code)
                        if referrer_profile.user_id != user.id:
                            profile.referred_by = referrer_profile.user
                            profile.save()
                    except Profile.DoesNotExist:
                        pass
                # Send welcome email (best-effort; skips silently if no ZeptoMail creds)
                _send_welcome_email(user, firstname)
                login(request, user)
                return _safe_redirect(request)
            except ValidationError as exc:
                error = ' '.join(exc.messages)
            except IntegrityError:
                error = 'An account with this email already exists. Try signing in.'
    elif request.method == 'GET':
        # Capture referral code from query string and stash in session
        ref = request.GET.get('ref', '').strip()
        if ref:
            request.session['ref_code'] = ref

    return render(request, 'authentication/signup.html', {
        'error': error,
        'ref_code': request.session.get('ref_code', ''),
    })


def _send_welcome_email(user, firstname):
    """Send a welcome email on signup (best-effort)."""
    try:
        from dashboard.services import send_email
    except Exception:
        return
    send_email(
        user.email,
        'Welcome to PONZI — Your Account Is Ready',
        f'<h3>Hi {firstname},</h3>'
        '<p>Welcome! Your account is now active.</p>'
        f'<p>Login anytime: <a href="{_full_url(reverse("authentication:login"))}">Login here</a></p>'
        '<p>Need help? Reply to this email or contact support.</p>',
        name=firstname,
    )


def logout_view(request):
    """Log the user out and return to the landing page."""
    logout(request)
    return redirect('dashboard:index')
