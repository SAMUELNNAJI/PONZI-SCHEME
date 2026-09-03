from django.shortcuts import render


def index(request):
    """Landing page."""
    return render(request, 'index.html')


def dashboard(request):
    """User dashboard.

    The `stats` context below is a placeholder base — replace the values
    with real data (from models / the logged-in user) when the backend
    grows. The current template ignores it, so nothing changes visually.
    """
    context = {
        'stats': {
            'balance': 0,
            'total_deposit': 0,
            'total_earned': 0,
            'active_plans': 0,
            'total_referrals': 0,
        },
    }
    return render(request, 'dashboard.html', context)


def plans(request):
    """All investment plans."""
    return render(request, 'plans.html')


def deposit(request):
    """Deposit page."""
    return render(request, 'deposit.html')


def withdraw(request):
    """Withdraw page."""
    return render(request, 'withdraw.html')


def history(request):
    """Transaction history."""
    return render(request, 'history.html')


def referrals(request):
    """Referrals page."""
    return render(request, 'referrals.html')


def settings_view(request):
    """Account settings."""
    return render(request, 'settings.html')


def login_view(request):
    """Login page (auth logic comes later)."""
    return render(request, 'login.html')


def signup_view(request):
    """Signup page (auth logic comes later)."""
    return render(request, 'signup.html')

# Create your views here.
