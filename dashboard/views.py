import json
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from adminpanel.models import SiteSetting, log_action
from authentication.models import Profile

from .models import Deposit, Notification, NotificationDismissal, Plan, Transaction, Withdrawal
from .services import (
    credit_wallet,
    get_available_balance,
    initialize_paystack_transaction,
    verify_paystack_transaction,
)


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

    # --- ROI & available balance ---
    # Latest approved deposit (the upgrade) determines the active plan & Daily ROI.
    active_deposits_list = list(
        approved_deposits.select_related('plan').filter(plan__isnull=False)
    )
    latest_deposit = active_deposits_list[0] if active_deposits_list else None

    # Active plan = the upgraded (latest) plan only
    active_plans = Plan.objects.none()
    if latest_deposit:
        active_plans = Plan.objects.filter(id=latest_deposit.plan_id, is_active=True)

    # Daily ROI from the upgraded plan on the upgraded amount
    daily_roi = Decimal('0')
    if latest_deposit:
        daily_roi = (
            latest_deposit.amount
            * Decimal(str(latest_deposit.plan.daily_percent))
            / Decimal('100')
        )

    # Total ROI earned so far, accruing at the upgraded plan's daily rate
    total_roi_earned = Decimal('0')
    if latest_deposit:
        started_at = latest_deposit.reviewed_at or latest_deposit.created_at
        days = max(1, (timezone.now() - started_at).days)
        total_roi_earned = daily_roi * days

    # Referral earnings (accumulated on the profile)
    referral_balance = profile.referral_balance or 0
    referred_count = User.objects.filter(profile__referred_by=user).count()

    # Pending + approved withdrawals reduce the available balance immediately
    total_withdrawals = user.withdrawals.filter(
        status__in=['pending', 'approved']
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    # Approved withdrawals only — for the "Total withdrawn" stat
    total_withdrawn = user.withdrawals.filter(
        status='approved'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    # Available balance = total daily ROI earned + referral earnings − withdrawals
    available_balance = total_roi_earned + Decimal(str(referral_balance)) - total_withdrawals
    if available_balance < 0:
        available_balance = Decimal('0')

    # Recent activity — transactions from the last 24 hours only
    since = timezone.now() - timezone.timedelta(hours=24)
    recent_activity = user.transactions.filter(created_at__gte=since).select_related(
        'deposit__plan', 'withdrawal'
    )[:10]

    # Notifications: all active ones shown in the info card
    all_notifications = Notification.objects.filter(is_active=True)

    # Modal: only show notifications the user hasn't dismissed yet
    dismissed_ids = NotificationDismissal.objects.filter(
        user=user
    ).values_list('notification_id', flat=True)
    undismissed_notifications = all_notifications.exclude(id__in=dismissed_ids)

    # Build referral link
    base_url = getattr(settings, 'SITE_BASE_URL', 'http://127.0.0.1:8000')
    referral_link = f'{base_url}/signup.html?ref={profile.referral_code}'

    context = {
        'stats': {
            'balance': available_balance,
            'total_deposit': total_deposit,
            'total_withdrawn': total_withdrawn,
            'daily_roi': daily_roi,
            'total_earned': referral_balance,
            'active_plans': active_plans.count(),
            'total_referrals': referred_count,
            'referral_balance': referral_balance,
        },
        'active_plans_list': active_plans,
        'active_deposits': active_deposits_list[:1],
        'recent_activity': recent_activity,
        'notifications': undismissed_notifications[:5],
        'all_notifications': all_notifications[:5],
        'latest_notification': undismissed_notifications.first(),
        'referral_link': referral_link,
        'referral_code': profile.referral_code,
    }
    return render(request, 'dashboard/dashboard.html', context)


@login_required
def deposit(request):
    """Deposit page + Paystack checkout handler.

    GET  — render the page with available plans and recent deposits.
    POST — validate input, create a *pending* Deposit record with a unique
           Paystack reference, then redirect the user to Paystack's hosted
           checkout to complete the payment.
    """
    plans = Plan.objects.filter(is_active=True)
    error = None
    selected_plan_id = request.GET.get('plan')
    if selected_plan_id and not selected_plan_id.isdigit():
        selected_plan_id = None
    else:
        selected_plan_id = int(selected_plan_id) if selected_plan_id else None

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
        elif not plan_id:
            error = 'Please select a plan before proceeding.'
        elif method not in ('bank', 'usdt'):
            error = 'Choose a valid payment method.'
        else:
            plan = Plan.objects.filter(id=plan_id, is_active=True).first() if plan_id else None
            paystack_ref = f'pw_{uuid.uuid4().hex}'
            callback_url = (
                f'{settings.SITE_BASE_URL}'
                f'{reverse("dashboard:paystack_callback")}'
            )

            auth_url, _ = initialize_paystack_transaction(
                request.user.email, amount, callback_url, paystack_ref,
            )

            if auth_url:
                dep = Deposit.objects.create(
                    user=request.user, plan=plan, amount=amount, method=method,
                    paystack_ref=paystack_ref,
                )
                Transaction.objects.create(
                    user=request.user, tx_type='deposit', amount=amount,
                    status='pending', deposit=dep,
                )
                log_action(
                    request.user,
                    f'Initiated a Paystack deposit of ₦{amount:,.0f} ({paystack_ref})',
                )
                # Send the user to Paystack to complete the payment
                return redirect(auth_url)
            else:
                error = (
                    'Could not initialize payment at this time. '
                    'Please try again in a moment.'
                )

    return render(request, 'dashboard/deposit.html', {
        'plans': plans,
        'selected_plan_id': selected_plan_id,
        'error': error,
        'submitted': request.GET.get('submitted') == '1',
        'paid': request.GET.get('paid') == '1',
        'pending': request.GET.get('pending') == '1',
        'failed': request.GET.get('failed') == '1',
        'recent_deposits': request.user.deposits.all()[:5],
    })


def paystack_callback(request):
    """Paystack redirect callback — verifies the payment and credits the wallet.

    Paystack sends the user's browser back here after the checkout flow
    (both success and failure).  We verify server-to-server with Paystack,
    then either approve the deposit + credit the wallet or mark it rejected.
    """
    reference = (
        request.GET.get('reference')
        or request.GET.get('trxref')
        or request.GET.get('ref_id')
    )

    if not reference:
        return redirect('/deposit.html?error=1')

    result = verify_paystack_transaction(reference)

    if not result:
        # Paystack unreachable / API error — don't assume failure, keep pending
        dep = Deposit.objects.filter(paystack_ref=reference).first()
        if dep and dep.status != 'rejected':
            dep.status = 'pending'
            dep.save(update_fields=['status'])
        return redirect('/deposit.html?pending=1')

    # ── Payment confirmed by Paystack → credit the wallet ──────────────
    if result and result.get('status') == 'success':
        try:
            dep = Deposit.objects.select_related('user', 'plan').get(
                paystack_ref=reference,
            )
        except Deposit.DoesNotExist:
            return redirect('/deposit.html?error=1')

        # Guard against double-crediting on repeat callbacks
        if dep.verified:
            return redirect('/deposit.html?paid=1')

        credit_wallet(dep)
        log_action(
            dep.user,
            f'Paid and confirmed deposit of ₦{dep.amount:,.0f} '
            f'({dep.get_method_display()})',
        )
        return redirect('/deposit.html?paid=1')

    # ── Payment is still being processed → keep it pending, NOT failed ──
    if result and result.get('status') in ('pending', 'processing'):
        dep = Deposit.objects.filter(paystack_ref=reference).first()
        if dep and dep.status != 'rejected':
            dep.status = 'pending'
            dep.save(update_fields=['status'])
        return redirect('/deposit.html?pending=1')

    # ── Payment failed, was abandoned, or Paystack reported failure ─────
    try:
        dep = Deposit.objects.get(paystack_ref=reference)
        dep.status = 'rejected'
        dep.save(update_fields=['status'])
    except Deposit.DoesNotExist:
        pass

    return redirect('/deposit.html?failed=1')


@csrf_exempt
def paystack_webhook(request):
    """Paystack server-to-server webhook — authoritative payment confirmation.

    Paystack POSTs signed events here (the URL is configured in the Paystack
    dashboard under Settings → Developer → Webhooks).  We verify the HMAC-SHA512
    ``x-paystack-signature`` header before touching any data, then credit the
    wallet on ``charge.success``.

    Unlike the browser redirect (*paystack_callback*), the webhook always runs —
    even if the customer closes the browser after paying.
    """
    from .services import verify_paystack_webhook_signature

    signature = request.headers.get('x-paystack-signature', '')

    if not settings.PAYSTACK_SECRET_KEY:
        return HttpResponse('PAYSTACK_SECRET_KEY is not configured.', status=500)

    if not signature or not verify_paystack_webhook_signature(request.body, signature):
        return HttpResponse('Invalid webhook signature.', status=400)

    try:
        payload = json.loads(request.body)
    except (ValueError, TypeError):
        return HttpResponse('Invalid JSON payload.', status=400)

    data = payload.get('data') or {}
    event = payload.get('event')
    reference = (
        data.get('reference')
        or data.get('trxref')
        or data.get('ref_id')
    )

    if reference:
        dep = Deposit.objects.select_related('user', 'plan').filter(
            paystack_ref=reference,
        ).first()

        if event == 'charge.success' and data.get('status') in (None, 'success'):
            # Payment confirmed → approve + credit the wallet (idempotent)
            if dep and not dep.verified:
                credit_wallet(dep)
                log_action(
                    dep.user,
                    f'Paid and confirmed deposit of ₦{dep.amount:,.0f} '
                    f'({dep.get_method_display()}) via webhook',
                )

        elif event in ('charge.pending', 'charge.processing'):
            # Money not yet received by Paystack → keep deposit pending (NOT failed)
            if dep and dep.status != 'approved':
                dep.status = 'pending'
                dep.save(update_fields=['status'])

        elif event in ('charge.failed', 'charge.abandoned'):
            # Payment definitely failed / was abandoned → mark rejected
            if dep and dep.status == 'pending':
                dep.status = 'rejected'
                dep.save(update_fields=['status'])

    # Always reply 200 to authenticated events so Paystack doesn't retry
    return JsonResponse({'status': 'success'})


@login_required
def withdraw(request):
    """Withdrawal page + request handler."""
    site = SiteSetting.load()
    error = None
    available_balance = get_available_balance(request.user)

    if request.method == 'POST':
        try:
            amount = round(float(request.POST.get('amount') or 0), 2)
        except ValueError:
            amount = 0
        method = request.POST.get('method', 'bank')

        if amount < float(site.min_withdraw):
            error = f'Minimum withdrawal is ₦{site.min_withdraw:,.0f}.'
        elif amount > float(available_balance):
            error = (
                f'Insufficient balance. You can withdraw up to '
                f'₦{available_balance:,.2f}.'
            )
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
        'available_balance': available_balance,
        'submitted': request.GET.get('submitted') == '1',
        'recent_withdrawals': request.user.withdrawals.select_related().all()[:10],
        'min_withdraw': site.min_withdraw,
    })


@login_required
def history(request):
    """Transaction history."""
    return render(request, 'dashboard/history.html', {
        'transactions': request.user.transactions.all()[:20],
    })


@login_required
def referrals(request):
    """Referrals page with real stats."""
    from django.db.models import Sum, Count, Q
    profile, _ = Profile.objects.get_or_create(user=request.user)

    # Annotate each referred profile with whether they have an approved deposit
    referred_profiles = Profile.objects.filter(
        referred_by=request.user
    ).select_related('user').annotate(
        has_active=Count(
            'user__deposits',
            filter=Q(user__deposits__status='approved'),
            distinct=True
        )
    )

    total_referrals = referred_profiles.count()
    active_referrals = referred_profiles.filter(has_active__gt=0).count()

    total_earnings = profile.referral_balance or 0

    from django.conf import settings as django_settings
    base_url = getattr(django_settings, 'SITE_BASE_URL', 'http://127.0.0.1:8000')
    referral_link = f'{base_url}/signup.html?ref={profile.referral_code}'

    return render(request, 'dashboard/referrals.html', {
        'profile': profile,
        'referred_profiles': referred_profiles,
        'total_referrals': total_referrals,
        'active_referrals': active_referrals,
        'total_earnings': total_earnings,
        'referral_link': referral_link,
    })


@login_required
def settings_view(request):
    """Account settings — handles profile update, password change, preferences."""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    user = request.user

    profile_success = False
    profile_error = None
    password_success = False
    password_error = None
    prefs_success = False

    if request.method == 'POST':
        action = request.POST.get('action')

        # ── Profile update ──────────────────────────────────────────
        if action == 'profile':
            first_name = request.POST.get('first_name', '').strip()
            last_name  = request.POST.get('last_name', '').strip()
            email      = request.POST.get('email', '').strip()
            phone      = request.POST.get('phone', '').strip()

            if not first_name:
                profile_error = 'First name is required.'
            elif not email:
                profile_error = 'Email address is required.'
            else:
                user.first_name = first_name
                user.last_name  = last_name
                user.email      = email
                user.save(update_fields=['first_name', 'last_name', 'email'])
                profile.phone = phone
                profile.save(update_fields=['phone'])
                profile_success = True

        # ── Password change ─────────────────────────────────────────
        elif action == 'password':
            current  = request.POST.get('current_password', '')
            new_pw   = request.POST.get('new_password', '')
            confirm  = request.POST.get('confirm_password', '')

            if not user.check_password(current):
                password_error = 'Current password is incorrect.'
            elif len(new_pw) < 8:
                password_error = 'New password must be at least 8 characters.'
            elif new_pw != confirm:
                password_error = 'New passwords do not match.'
            else:
                user.set_password(new_pw)
                user.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                password_success = True

        # ── Preferences ─────────────────────────────────────────────
        elif action == 'preferences':
            profile.notif_email    = request.POST.get('notif_email') == 'on'
            profile.notif_roi      = request.POST.get('notif_roi') == 'on'
            profile.notif_referral = request.POST.get('notif_referral') == 'on'
            profile.currency       = request.POST.get('currency', 'NGN')
            profile.language       = request.POST.get('language', 'en')
            profile.save(update_fields=['notif_email', 'notif_roi', 'notif_referral', 'currency', 'language'])
            prefs_success = True

    return render(request, 'dashboard/settings.html', {
        'profile': profile,
        'profile_success': profile_success,
        'profile_error': profile_error,
        'password_success': password_success,
        'password_error': password_error,
        'prefs_success': prefs_success,
    })


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
