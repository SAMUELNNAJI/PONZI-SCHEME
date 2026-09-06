"""Shared business logic: wallet credits, referral rewards, emails, admin payouts."""
from decimal import Decimal
import hashlib
import hmac
import logging
import urllib.error
import urllib.request
import json
from django.conf import settings
from django.utils import timezone

from dashboard.models import Deposit, Withdrawal, Transaction
from authentication.models import Profile

logger = logging.getLogger(__name__)

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


def get_available_balance(user):
    """Available balance = total daily ROI earned + referral earnings − withdrawals.

    Daily ROI accrues on the *latest approved* (upgraded) plan and deposit.
    Both pending and approved withdrawals reduce the available balance as soon
    as a withdrawal request is made.
    """
    from django.db.models import Sum

    deposits = list(
        Deposit.objects.filter(user=user, status='approved')
        .select_related('plan')
        .filter(plan__isnull=False)
    )
    latest = deposits[0] if deposits else None

    total_roi_earned = Decimal('0')
    if latest:
        daily = (
            latest.amount * Decimal(str(latest.plan.daily_percent)) / Decimal('100')
        )
        started_at = latest.reviewed_at or latest.created_at
        days = max(1, (timezone.now() - started_at).days)
        total_roi_earned = daily * days

    try:
        referral = user.profile.referral_balance or Decimal('0')
    except Profile.DoesNotExist:
        referral = Decimal('0')

    withdrawn = Withdrawal.objects.filter(
        user=user, status__in=['pending', 'approved'],
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    available = total_roi_earned + Decimal(str(referral)) - withdrawn
    return available if available > 0 else Decimal('0')


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


# ---------------------------------------------------------------------------
# Paystack payment gateway
# ---------------------------------------------------------------------------
def _paystack_headers():
    """Return auth headers for Paystack API requests.

    A ``User-Agent`` is REQUIRED: Paystack sits behind Cloudflare, which
    blocks requests signed by Python's default ``Python-urllib/x`` agent
    with HTTP 403 / Cloudflare error 1010 ("browser signature banned").
    """
    secret = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {secret}',
        'User-Agent': 'Mozilla/5.0 (compatible; PaystackClient/1.0)',
        'Accept': 'application/json',
    }


def initialize_paystack_transaction(email, amount, callback_url, reference):
    """Initialize a Paystack transaction.

    Returns ``(authorization_url, reference)`` on success, ``(None, None)``
    on failure.  *amount* is in NGN and is converted to kobo (×100) for
    the Paystack API.
    """
    if not settings.PAYSTACK_SECRET_KEY:
        print('[paystack] PAYSTACK_SECRET_KEY is not set — skipping init')
        return None, None

    payload = json.dumps({
        'email': email,
        'amount': int(amount * 100),          # NGN → kobo
        'reference': reference,
        'callback_url': callback_url,
        'currency': 'NGN',
    })
    req = urllib.request.Request(
        'https://api.paystack.co/transaction/initialize',
        data=payload.encode('utf-8'),
        method='POST',
        headers=_paystack_headers(),
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        if data.get('status'):
            return data['data'].get('authorization_url'), data['data'].get('reference')
        logger.error(f'[paystack-init] API error: {data.get("message")}')
        return None, None
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode('utf-8', 'replace')[:300]
        except Exception:
            pass
        logger.error(f'[paystack-init] HTTP {e.code} from Paystack: {body}')
        return None, None
    except Exception as e:
        logger.error(f'[paystack-init-error] {type(e).__name__}: {e}')
        return None, None


def verify_paystack_transaction(reference):
    """Verify a Paystack transaction by reference.

    Returns the Paystack ``data`` dict on success (with ``status == 'success'``)
    or ``None`` if verification fails.
    """
    if not settings.PAYSTACK_SECRET_KEY:
        return None

    req = urllib.request.Request(
        f'https://api.paystack.co/transaction/verify/{reference}',
        method='GET',
        headers=_paystack_headers(),
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        if data.get('status'):
            return data['data']
        logger.error(f'[paystack-verify] API error: {data.get("message")}')
        return None
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode('utf-8', 'replace')[:300]
        except Exception:
            pass
        logger.error(f'[paystack-verify] HTTP {e.code} from Paystack: {body}')
        return None
    except Exception as e:
        logger.error(f'[paystack-verify-error] {type(e).__name__}: {e}')
        return None


def verify_paystack_webhook_signature(body, signature):
    """Verify the ``x-paystack-signature`` header over the raw request body.

    Paystack signs every webhook with HMAC-SHA512 using the secret key.  Returns
    ``True`` only for a valid signature.  The *body* must be the raw, un-decoded
    bytes so the hash matches what Paystack signed.
    """
    secret = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    if not secret or not signature:
        return False
    digest = hmac.new(
        secret.encode('utf-8'), body, hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(digest, signature)


def build_paystack_webhook_url():
    """Absolute URL Paystack should POST webhook events to."""
    base = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')
    return f'{base}/paystack/webhook'


def build_paystack_callback_url():
    """Absolute URL Paystack redirects the browser to after checkout."""
    base = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')
    return f'{base}/paystack/callback'
