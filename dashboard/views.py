from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def index(request):
    """Landing page (public)."""
    return render(request, 'index.html')


@login_required
def plans(request):
    """All investment plans."""
    return render(request, 'plans.html')


@login_required
def dashboard(request):
    """User dashboard.

    The `stats` context below is a placeholder base — replace the values
    with real data (from models tied to request.user) when the backend
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


@login_required
def deposit(request):
    """Deposit page."""
    return render(request, 'deposit.html')


@login_required
def withdraw(request):
    """Withdraw page."""
    return render(request, 'withdraw.html')


@login_required
def history(request):
    """Transaction history."""
    return render(request, 'history.html')


@login_required
def referrals(request):
    """Referrals page."""
    return render(request, 'referrals.html')


@login_required
def settings_view(request):
    """Account settings."""
    return render(request, 'settings.html')
