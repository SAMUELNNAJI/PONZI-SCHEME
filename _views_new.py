from decimal import Decimal, InvalidOperation
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from adminpanel.models import SiteSetting, log_action
from dashboard.models import (
    Deposit, Notification, Plan, Transaction, Withdrawal,
)
from .models import ActivityLog

admin_required = staff_member_required(login_url='/login.html')

DEFAULT_PLANS = [
    ('Starter Plan', 'basic', 7000, False),
    ('Classy Plan', 'basic', 15000, False),
    ('Royal Plan', 'premium', 42000, False),
    ('Deluxe Plan', 'premium', 151000, False),
    ('Business Suit', 'popular', 250000, True),
    ('Empire Plan', 'premium', 451000, False),
    ('Platinum Plan', 'value', 720000, False),
    ('Gold Plan', 'hot', 1000000, False),
    ('Diamond Plan', 'diamond', 2500000, False),
    ('Premium Elite', 'vip', 5000000, True),
]


def _dec(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


# --- 1. Users ---
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


# --- 2. Plans ---
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
            plan.badge_text = request.POST.get('badge_text', '').strip()
            plan.badge_gradient_from = request.POST.get('badge_gradient_from', '#FF6B6B') or '#FF6B6B'
            plan.badge_gradient_to = request.POST.get('badge_gradient_to', '#F7971E') or '#F7971E'
            plan.accent = request.POST.get('accent') == 'on'
            plan.daily_percent = percent
            plan.duration_days = int(days)
            plan.price = price
            plan.is_active = request.POST.get('is_active') == 'on'
            plan.sort_order = int(request.POST.get('sort_order') or 0)
            plan.save()
            return redirect('adminpanel:plans')

    return render(request, 'adminpanel/plan_form.html', {
        'plan': plan,
        'error': error,
        'badges': Plan.BADGES,
    })