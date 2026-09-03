from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render

from adminpanel.models import SiteSetting, log_action

from .models import Deposit, Notification, Plan, Transaction, Withdrawal


def index(request):
    """Landing page (public)."""
    return render(request, 'index.html')


@login_required
def plans(request):
    """All investment plans, rendered from the database."""
    return render(request, 'plans.html', {
        'plans': Plan.objects.filter(is_active=True),
    })


@login_required
def dashboard(request):
    """User dashboard — includes admin notifications."""
    user = request.user
    context = {
        'stats': {
            'balance': 0,
            'total_deposit': user.deposits.filter(status='approved')
                .aggregate(t=Sum('amount'))['t'] or 0,
            'total_earned': 0,
            'active_plans': 0,
            'total_referrals': 0,
        },
        'notifications': Notification.objects.filter(is_active=True)[:5],
    }
    return render(request, 'dashboard.html', context)


@login_required
def deposit(request):
    """Deposit page + submission handler."""
    plans = Plan.objects.filter(is_active=True)
    error = None

    if request.method == 'POST':
        site = SiteSetting.load()
        try:
            amount = round(float(request.POST.get('amount') or 0), 2)
        except ValueError:
            amount = 0
        method = request.POST.get('method', 'bank')
        plan_id = request.POST.get('plan')

        if amount < float(site.min_deposit):
            error = f'Minimum deposit is ₦{site.min_deposit:,.0f}.'
        elif method not in ('bank', 'usdt'):
            error = 'Choose a valid payment method.'
        else:
            plan = Plan.objects.filter(id=plan_id, is_active=True).first() if plan_id else None
            dep = Deposit.objects.create(
                user=request.user, plan=plan, amount=amount, method=method,
            )
            Transaction.objects.create(
                user=request.user, tx_type='deposit', amount=amount,
                status='pending', deposit=dep,
            )
            log_action(request.user, f'Submitted a deposit of ₦{amount:,.0f}')
            return redirect('/deposit.html?submitted=1')

    return render(request, 'deposit.html', {
        'plans': plans,
        'error': error,
        'submitted': request.GET.get('submitted') == '1',
        'recent_deposits': request.user.deposits.all()[:5],
    })


@login_required
def withdraw(request):
    """Withdrawal page + request handler."""
    site = SiteSetting.load()
    error = None

    if request.method == 'POST':
        try:
            amount = round(float(request.POST.get('amount') or 0), 2)
        except ValueError:
            amount = 0
        method = request.POST.get('method', 'bank')

        if amount < float(site.min_withdraw):
            error = f'Minimum withdrawal is ₦{site.min_withdraw:,.0f}.'
        elif method not in ('bank', 'usdt'):
            error = 'Choose a valid payout method.'
        elif method == 'bank' and not (
            request.POST.get('bank') and request.POST.get('acct')
            and request.POST.get('acct_name')
        ):
            error = 'Fill in your bank name, account number and account name.'
        elif method == 'usdt' and not request.POST.get('usdt_addr'):
            error = 'Enter your USDT TRC20 wallet address.'
        else:
            wd = Withdrawal.objects.create(
                user=request.user,
                amount=amount,
                method=method,
                bank_name=request.POST.get('bank', ''),
                account_number=request.POST.get('acct', ''),
                account_name=request.POST.get('acct_name', ''),
                usdt_address=request.POST.get('usdt_addr', ''),
            )
            Transaction.objects.create(
                user=request.user, tx_type='withdrawal', amount=amount,
                status='pending', withdrawal=wd,
            )
            log_action(request.user, f'Requested a withdrawal of ₦{amount:,.0f}')
            return redirect('/withdraw.html?submitted=1')

    return render(request, 'withdraw.html', {
        'error': error,
        'submitted': request.GET.get('submitted') == '1',
        'recent_withdrawals': request.user.withdrawals.all()[:5],
    })


@login_required
def history(request):
    """Transaction history."""
    return render(request, 'history.html', {
        'transactions': request.user.transactions.all()[:20],
    })


@login_required
def referrals(request):
    """Referrals page."""
    return render(request, 'referrals.html')


@login_required
def settings_view(request):
    """Account settings."""
    return render(request, 'settings.html')
