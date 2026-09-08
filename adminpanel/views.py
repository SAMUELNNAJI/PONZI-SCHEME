from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from adminpanel.models import SiteSetting, log_action
from dashboard.models import (
    Deposit,
    Notification,
    Plan,
    Transaction,
    Withdrawal,
)

from .models import ActivityLog

# Staff-gated views redirect to OUR login page (not Django admin's).
admin_required = staff_member_required(login_url='/login.html')

DEFAULT_PLANS = [
    ('Starter Plan',   'basic',   7000,     False),
    ('Classy Plan',    'basic',   15000,    False),
    ('Royal Plan',     'premium', 42000,    False),
    ('Deluxe Plan',    'premium', 151000,   False),
    ('Business Suit',  'popular', 250000,   True),
    ('Empire Plan',    'premium', 451000,   False),
    ('Platinum Plan',  'value',   720000,   False),
    ('Gold Plan',      'hot',     1000000,  False),
    ('Diamond Plan',   'diamond', 2500000,  False),
    ('Premium Elite',  'vip',     5000000,  True),
]


def _dec(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


# ── 1. Users ────────────────────────────────────────────────────────────
@admin_required
def users(request):
    users_list = User.objects.select_related('profile').annotate(
        deposit_total=Sum('deposits__amount', filter=Q(deposits__status='approved')),
    ).order_by('-date_joined')

    if request.method == 'POST':
        target = get_object_or_404(User, pk=request.POST.get('pk'))
        action = request.POST.get('action')
        if target != request.user:
            if action == 'toggle_active':
                target.is_active = not target.is_active
                target.save()
                state = 'Enabled' if target.is_active else 'Disabled'
                log_action(request.user, f'{state} account for {target.username}')
            elif action == 'toggle_staff':
                target.is_staff = not target.is_staff
                target.save()
                state = 'Granted' if target.is_staff else 'Revoked'
                log_action(request.user, f'{state} staff access for {target.username}')
        return redirect('adminpanel:users')

    return render(request, 'adminpanel/users.html', {'users_list': users_list})


# ── 2. Plans ────────────────────────────────────────────────────────────
@admin_required
def plans(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'import':
            created = 0
            for order, (name, badge, price, accent) in enumerate(DEFAULT_PLANS):
                _, was_created = Plan.objects.get_or_create(
                    name=name,
                    defaults={'badge': badge, 'price': price, 'accent': accent,
                              'daily_percent': 3, 'duration_days': 30, 'sort_order': order},
                )
                created += int(was_created)
            log_action(request.user, f'Imported default plans ({created} new)')
        elif action == 'delete':
            plan = get_object_or_404(Plan, pk=request.POST.get('pk'))
            name = plan.name
            plan.delete()
            log_action(request.user, f'Deleted plan "{name}"')
        return redirect('adminpanel:plans')

    return render(request, 'adminpanel/plans.html', {
        'plans_list': Plan.objects.all(),
    })


@admin_required
def plan_form(request, pk=None):
    plan = get_object_or_404(Plan, pk=pk) if pk else None
    error = None

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        price = _dec(request.POST.get('price'))
        percent = _dec(request.POST.get('daily_percent'))
        days = request.POST.get('duration_days')
        if not name or price is None or price <= 0 or percent is None or not days:
            error = 'Fill in a valid name, price, percent and duration.'
        else:
            if plan is None:
                plan = Plan()
                log_action(request.user, f'Added new plan "{name}"')
            else:
                log_action(request.user, f'Updated plan "{name}"')
            plan.name = name
            plan.badge = request.POST.get('badge', 'basic')
            plan.accent = request.POST.get('accent') == 'on'
            plan.daily_percent = percent
            plan.duration_days = int(days)
            plan.price = price
            plan.is_active = request.POST.get('is_active') == 'on'
            plan.sort_order = int(request.POST.get('sort_order') or 0)
            plan.badge_text = request.POST.get('badge_text', '').strip()
            plan.badge_gradient_from = request.POST.get('badge_gradient_from', '#FF6B6B') or '#FF6B6B'
            plan.badge_gradient_to = request.POST.get('badge_gradient_to', '#F7971E') or '#F7971E'
            plan.save()
            return redirect('adminpanel:plans')

    return render(request, 'adminpanel/plan_form.html', {
        'plan': plan,
        'error': error,
        'badges': Plan.BADGES,
    })

# ── 3. Deposits ─────────────────────────────────────────────────────────
@admin_required
def deposits(request):
    from django.core.paginator import Paginator
    from django.utils import timezone
    from dashboard.services import credit_wallet

    if request.method == 'POST':
        dep = get_object_or_404(Deposit, pk=request.POST.get('pk'))
        action = request.POST.get('action')
        # Only USDT deposits need manual approval
        if dep.method == 'usdt' and dep.status == 'pending':
            if action == 'approve':
                credit_wallet(dep)
                log_action(request.user,
                    f'Approved USDT deposit #{dep.id} (₦{dep.amount:,.0f}) '
                    f'for {dep.user.username}')
            elif action == 'reject':
                dep.status = 'rejected'
                dep.reviewed_at = timezone.now()
                dep.save(update_fields=['status', 'reviewed_at'])
                dep.transactions.update(status='rejected')
                log_action(request.user,
                    f'Rejected USDT deposit #{dep.id} (₦{dep.amount:,.0f}) '
                    f'for {dep.user.username}')
        return redirect('adminpanel:deposits')

    all_deposits = Deposit.objects.select_related('user', 'plan').order_by('-created_at')
    paginator = Paginator(all_deposits, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'adminpanel/deposits.html', {
        'page_obj': page_obj,
        'total': all_deposits.count(),
    })


# ── 4. Withdrawals ──────────────────────────────────────────────────────
@admin_required
def withdrawals(request):
    from django.core.paginator import Paginator
    from django.utils import timezone

    if request.method == 'POST':
        wd = get_object_or_404(Withdrawal, pk=request.POST.get('pk'))
        action = request.POST.get('action')
        if wd.status == 'pending' and action in ('approve', 'reject'):
            wd.status = 'approved' if action == 'approve' else 'rejected'
            wd.reviewed_at = timezone.now()
            wd.save()
            wd.transactions.update(status=wd.status)
            log_action(request.user, f'{wd.status.title()} withdrawal #{wd.id} '
                                     f'(₦{wd.amount:,.0f}) by {wd.user.username}')
        return redirect('adminpanel:withdrawals')

    today = timezone.localdate()

    today_qs = Withdrawal.objects.select_related('user').filter(
        created_at__date=today
    ).order_by('-created_at')

    past_qs = Withdrawal.objects.select_related('user').exclude(
        created_at__date=today
    ).order_by('-created_at')

    today_paginator = Paginator(today_qs, 20)
    past_paginator = Paginator(past_qs, 20)

    today_page = today_paginator.get_page(request.GET.get('page_today'))
    past_page = past_paginator.get_page(request.GET.get('page_past'))

    return render(request, 'adminpanel/withdrawals.html', {
        'today_page': today_page,
        'past_page': past_page,
        'today_total': today_qs.count(),
        'past_total': past_qs.count(),
    })


# ── 5. Transactions ─────────────────────────────────────────────────────
@admin_required
def transactions(request):
    return render(request, 'adminpanel/transactions.html', {
        'transactions_list': Transaction.objects.select_related('user'),
    })


# ── 6. Notify ───────────────────────────────────────────────────────────
@admin_required
def notify(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            title = request.POST.get('title', '').strip()
            body = request.POST.get('body', '').strip()
            if title and body:
                Notification.objects.create(title=title, body=body)
                log_action(request.user, f'Published notification "{title}"')
        elif action == 'toggle':
            note = get_object_or_404(Notification, pk=request.POST.get('pk'))
            note.is_active = not note.is_active
            note.save()
            state = 'Activated' if note.is_active else 'Hid'
            log_action(request.user, f'{state} notification "{note.title}"')
        elif action == 'delete':
            note = get_object_or_404(Notification, pk=request.POST.get('pk'))
            title = note.title
            note.delete()
            log_action(request.user, f'Deleted notification "{title}"')
        return redirect('adminpanel:notify')

    return render(request, 'adminpanel/notify.html', {
        'notifications': Notification.objects.all(),
    })


# ── 7. Settings ─────────────────────────────────────────────────────────
@admin_required
def settings_view(request):
    site = SiteSetting.load()
    saved = False

    if request.method == 'POST':
        min_dep = _dec(request.POST.get('min_deposit'))
        min_wd = _dec(request.POST.get('min_withdraw'))
        if min_dep is not None and min_wd is not None:
            site.site_name = request.POST.get('site_name', site.site_name).strip()
            site.support_email = request.POST.get('support_email', site.support_email).strip()
            site.min_deposit = min_dep
            site.min_withdraw = min_wd
            site.usdt_bep20_address = request.POST.get('usdt_bep20_address', '').strip()
            site.save()
            log_action(request.user, 'Updated site settings')
            saved = True

    return render(request, 'adminpanel/settings.html', {'site': site, 'saved': saved})


# ── 8. Logs ─────────────────────────────────────────────────────────────
@admin_required
def logs(request):
    return render(request, 'adminpanel/logs.html', {
        'logs_list': ActivityLog.objects.all()[:200],
    })


# ── 9. Payments (Paystack config helper) ────────────────────────────────
@admin_required
def payments(request):
    """Show the exact URLs to add in the Paystack dashboard + key status.

    The webhook URL is where Paystack server-to-server POSTs payment events
    (Settings → Developer → Webhooks).  The callback URL is where the customer's
    browser is redirected after checkout (Settings → Developer → Callback URL).
    """
    from dashboard.services import build_paystack_callback_url, build_paystack_webhook_url

    return render(request, 'adminpanel/payments.html', {
        'webhook_url': build_paystack_webhook_url(),
        'callback_url': build_paystack_callback_url(),
        'public_key_set': bool(getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')),
        'secret_key_set': bool(getattr(settings, 'PAYSTACK_SECRET_KEY', '')),
        'mode': getattr(settings, 'PAYSTACK_MODE', 'test'),
        'base_url': getattr(settings, 'SITE_BASE_URL', ''),
    })
