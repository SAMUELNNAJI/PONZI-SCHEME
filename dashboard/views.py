from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from adminpanel.models import SiteSetting, log_action
from authentication.models import Profile

from .models import Deposit, Notification, NotificationDismissal, Plan, Transaction, Withdrawal


def index(request):
    """Landing page (public)."""
    return render(request, 'dashboard/index.html')


def terms(request):
    """Terms of Service page (public)."""
    return render(request, 'dashboard/terms.html')


def privacy(request):
    """Privacy Policy page (public)."""
    return render(request, 'dashboard/privacy.html')


@login_required
def plans(request):
    """All investment plans, rendered from the database."""
    return render(request, 'dashboard/plans.html', {
        'plans': Plan.objects.filter(is_active=True),
    })


@login_required
def dashboard(request):
    """User dashboard — includes admin notifications."""
    user = request.user
    # Ensure profile always exists (auto-create if missing)
    profile, _ = Profile.objects.get_or_create(user=user)
    approved_deposits = user.deposits.filter(status='approved')
    total_deposit = approved_deposits.aggregate(t=Sum('amount'))['t'] or 0

    # Get active plans from approved deposits (unique plans)
    active_plan_ids = approved_deposits.values_list('plan', flat=True).distinct()
    active_plans = Plan.objects.filter(id__in=active_plan_ids, is_active=True)

    # Referral balance from profile
    referral_balance = profile.referral_balance or 0
    referred_count = User.objects.filter(profile__referred_by=user).count()

    # Total balance = approved deposits + referral earnings
    balance = total_deposit + referral_balance

    # Notifications: exclude ones the user has dismissed
    dismissed_ids = NotificationDismissal.objects.filter(
        user=user
    ).values_list('notification_id', flat=True)
    active_notifications = Notification.objects.filter(is_active=True).exclude(
        id__in=dismissed_ids
    )

    # Build referral link
    from django.conf import settings
    base_url = getattr(settings, 'SITE_BASE_URL', 'http://127.0.0.1:8000')
    referral_link = f'{base_url}/signup.html?ref={profile.referral_code}'

    context = {
        'stats': {
            'balance': balance,
            'total_deposit': total_deposit,
            'total_earned': referral_balance,
            'active_plans': active_plans.count(),
            'total_referrals': referred_count,
            'referral_balance': referral_balance,
        },
        'active_plans_list': active_plans,
        'notifications': active_notifications[:5],
        'latest_notification': active_notifications.first(),
        'referral_link': referral_link,
        'referral_code': profile.referral_code,
    }
    return render(request, 'dashboard/dashboard.html', context)


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

    return render(request, 'dashboard/deposit.html', {
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

    return render(request, 'dashboard/withdraw.html', {
        'error': error,
        'submitted': request.GET.get('submitted') == '1',
        'recent_withdrawals': request.user.withdrawals.all()[:5],
    })


@login_required
def history(request):
    """Transaction history."""
    return render(request, 'dashboard/history.html', {
        'transactions': request.user.transactions.all()[:20],
    })


@login_required
def referrals(request):
    """Referrals page."""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    referred_users = Profile.objects.filter(referred_by=request.user).select_related('user')
    return render(request, 'dashboard/referrals.html', {
        'profile': profile,
        'referred_users': referred_users,
    })


@login_required
def settings_view(request):
    """Account settings."""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return render(request, 'dashboard/settings.html', {'profile': profile})


@login_required
@require_POST
def dismiss_notification(request):
    """Mark a notification as dismissed for the current user (AJAX)."""
    notification_id = request.POST.get('notification_id')
    if notification_id:
        notification = Notification.objects.filter(id=notification_id, is_active=True).first()
        if notification:
            NotificationDismissal.objects.get_or_create(
                user=request.user, notification=notification
            )
            return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)
