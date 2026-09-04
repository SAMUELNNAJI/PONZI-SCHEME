"""Shared business logic: wallet credits, referral rewards, emails, admin payouts."""
from decimal import Decimal
import urllib.error
import urllib.request
import json
from django.conf import settings
from django.utils import timezone

from dashboard.models import Deposit, Withdrawal, Transaction
from authentication.models import Profile

MIN_WITHDRAWAL = Decimal('5000.00')
REFERRAL_COMMISSION_RATE = Decimal('10')  # 10% of deposit goes to referrer


class InsufficientBalance(Exception):
    """Raised when a user cannot withdraw."""


class WithdrawalLimitExceeded(Exception):
    """Raised when a user has already requested a withdrawal today."""


# ---------------------------------------------------------------------------
# Wallet / deposit
# ---------------------------------------------------------------------------
def get_wallet_balance(user):
    """Return the live wallet balance (approved deposits minus approved withdrawals)."""
    from django.db.models import Sum
    pos = Deposit.objects.filter(user=user, status='approved').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    neg = Withdrawal.objects.filter(user=user, status='approved').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    return pos - neg


def credit_wallet(deposit):
    """Approve a deposit, credit the wallet, fire referral commission, create a transaction."""
    deposit.status = 'approved'
    deposit.admin_confirmed = True
    deposit.verified = True
    deposit.reviewed_at = timezone.now()
    deposit.save(update_fields=['status', 'admin_confirmed', 'verified', 'reviewed_at'])
    Transaction.objects.create(
        user=deposit.user,
        tx_type='deposit',
        amount=deposit.amount,
        status='approved',
        deposit=deposit,
    )
    credit_referrals(deposit)


def credit_referrals(deposit):
    """Give the referrer REFERRAL_COMMISSION_RATE% of the deposit."""
    try:
        profile = deposit.user.profile
    except Profile.DoesNotExist:
        return
    referrer_profile = Profile.objects.select_related('user').filter(
        referral_code=profile.referred_by_ref_code()
    ).first()
    if not referrer_profile:
        return
    commission = (deposit.amount * REFERRAL_COMMISSION_RATE / 100).quantize(Decimal('0.01'))
    if commission <= 0:
        return
    referrer_profile.referral_balance += commission
    referrer_profile.save(update_fields=['referral_balance'])
    Transaction.objects.create(
        user=referrer_profile.user,
        tx_type='referral',
        amount=commission,
        status='approved',
    )


# ---------------------------------------------------------------------------
# Withdrawal gates
# ---------------------------------------------------------------------------
def can_request_withdrawal(user):
    """Return (ok: bool, reason: str|None). Enforces balance + once-per-day."""
    balance = get_wallet_balance(user)
    if balance < MIN_WITHDRAWAL:
        return False, f'You need at least ₦{MIN_WITHDRAWAL:,} to withdraw.'
    today_min = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if Withdrawal.objects.filter(
        user=user, requested_at__gte=today_min, status='pending'
    ).exists():
        return False, 'You can only submit one withdrawal request per day.'
    return True, None


def request_withdrawal(user, amount, method, **details):
    """Create a withdrawal request after validation."""
    amount = Decimal(str(amount))
    ok, reason = can_request_withdrawal(user)
    if not ok:
        raise InsufficientBalance(reason)
    w = Withdrawal.objects.create(
        user=user,
        amount=amount,
        method=method,
        requested_at=timezone.now(),
        **details,
    )
    Transaction.objects.create(
        user=user,
        tx_type='withdrawal',
        amount=amount,
        status='pending',
        withdrawal=w,
    )
    return w


def mark_withdrawal_paid(withdrawal):
    """Admin action: mark as paid → status approved + paid=True + notify + email."""
    withdrawal.status = 'approved'
    withdrawal.paid = True
    withdrawal.reviewed_at = timezone.now()
    withdrawal.save(update_fields=['status', 'paid', 'reviewed_at'])
    Transaction.objects.filter(withdrawal=withdrawal).update(status='approved')
    send_email(
        withdrawal.user.email,
        'Withdrawal Request Paid',
        f'Your withdrawal of ₦{withdrawal.amount:,.2f} has been processed and sent to {withdrawal.account_name or "your"} account.',
    )


# ---------------------------------------------------------------------------
# Emails via ZeptoMail
# ---------------------------------------------------------------------------
def send_email(to_email, subject, body_html, name=''):
    """Send an email via ZeptoMail (silently skip if credentials are missing)."""
    if not settings.ZEPTOMAIL_CLIENT_ID or not settings.ZEPTOMAIL_CLIENT_SECRET:
        print(f"[email-skip] {to_email} | {subject}")
        return False
    payload = {
        "request_type": "transactional",
        "recipients": [{"email_address": {"email": to_email, "name": name or to_email}}],
        "from": {"email_address": {"email": settings.DEFAULT_FROM_EMAIL}},
        "subject": subject,
        "htmlbody": body_html,
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        "https://email.zoho.com/api/v1/mail",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Zoho-oAuthAccessToken=" + _get_zm_token(),
        },
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"[email-error] {to_email} | {subject} | {e}")
        return False


def _get_zm_token():
    """Exchange client credentials for a ZeptoMail access token."""
    data = json.dumps({
        "client_id": settings.ZEPTOMAIL_CLIENT_ID,
        "client_secret": settings.ZEPTOMAIL_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }).encode('utf-8')
    req = urllib.request.Request(
        "https://email.zoho.com/oauth/v2/token",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())["access_token"]
    except Exception as e:
        print(f"[zm-token-error] {e}")
        return ""


def notify_users(notification):
    """Email every active user about an admin notification."""
    from django.contrib.auth.models import User
    sent = 0
    for u in User.objects.filter(is_active=True, email__isnull=False):
        sent += 1 if send_email(
            u.email,
            f"New Notice: {notification.title}",
            f"<h3>{notification.title}</h3><p>{notification.body}</p>",
            name=u.get_full_name() or u.username,
        ) else 0
    if sent:
        notification.email_sent = True
        notification.save(update_fields=['email_sent'])
    return sent
