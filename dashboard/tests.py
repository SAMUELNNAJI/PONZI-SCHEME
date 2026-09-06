from decimal import Decimal
import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from datetime import timedelta

from dashboard.models import Deposit, Plan, Withdrawal
from dashboard.services import (
    build_paystack_callback_url,
    build_paystack_webhook_url,
    get_available_balance,
    verify_paystack_webhook_signature,
)


class AvailableBalanceTests(TestCase):
    """Available balance = total daily ROI earned + referral earnings − withdrawals."""

    def setUp(self):
        self.user = User.objects.create_user('tester', 't@t.com', 'x12345678')
        self.plan = Plan.objects.create(
            name='Basic', price=Decimal('10000'), daily_percent=Decimal('3'),
            duration_days=30,
        )

    def test_deposit_earns_roi_from_approved_deposit(self):
        dep = Deposit.objects.create(
            user=self.user, plan=self.plan, amount=Decimal('10000'),
            status='approved',
        )
        dep.reviewed_at = timezone.now() - timedelta(days=2)
        dep.save(update_fields=['reviewed_at'])

        # 10,000 @ 3% = 300/day × 2 days (reviewed 2 days ago) = 600
        bal = get_available_balance(self.user)
        self.assertGreaterEqual(bal, Decimal('600'))
        self.assertLessEqual(bal, Decimal('900'))

    def test_pending_withdrawal_reduces_balance(self):
        Deposit.objects.create(
            user=self.user, plan=self.plan, amount=Decimal('10000'),
            status='approved', reviewed_at=timezone.now() - timedelta(days=1),
        )
        Withdrawal.objects.create(user=self.user, amount=Decimal('500'))

        bal = get_available_balance(self.user)  # 300 − 500 → clamped to 0
        self.assertGreaterEqual(bal, Decimal('0'))
        self.assertLessEqual(bal, Decimal('300'))

    def test_withdrawal_cannot_exceed_available_balance(self):
        Deposit.objects.create(
            user=self.user, plan=self.plan, amount=Decimal('10000'),
            status='approved', reviewed_at=timezone.now(),
        )
        client = Client()
        client.force_login(self.user)
        resp = client.post('/withdraw.html', {
            'amount': '9999999', 'method': 'bank',
            'bank': 'Test Bank', 'acct': '0123456789', 'acct_name': 'Tester',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Insufficient balance')


class DashboardUpgradeTests(TestCase):
    """After upgrading, dashboard shows only the upgraded plan + its daily ROI."""

    def setUp(self):
        self.user = User.objects.create_user('tester2', 't2@t.com', 'x12345678')
        self.basic = Plan.objects.create(
            name='Basic', price=Decimal('10000'), daily_percent=Decimal('3'),
            duration_days=30,
        )
        self.premium = Plan.objects.create(
            name='Premium', price=Decimal('50000'), daily_percent=Decimal('5'),
            duration_days=30,
        )

    def test_dashboard_uses_upgraded_plan_only(self):
        Deposit.objects.create(
            user=self.user, plan=self.basic, amount=Decimal('10000'),
            status='approved', reviewed_at=timezone.now() - timedelta(days=3),
        )
        Deposit.objects.create(
            user=self.user, plan=self.premium, amount=Decimal('50000'),
            status='approved', reviewed_at=timezone.now() - timedelta(days=1),
        )

        client = Client()
        client.force_login(self.user)
        resp = client.get('/dashboard.html')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()

        # Upgraded plan is shown in "Active investments"
        self.assertIn('Premium', html)
        # Daily ROI stat comes from the upgraded plan: 50,000 @ 5% = 2,500
        self.assertIn('2,500.00', html)

    def test_dashboard_passes_available_balance(self):
        Deposit.objects.create(
            user=self.user, plan=self.premium, amount=Decimal('50000'),
            status='approved',
        )
        client = Client()
        client.force_login(self.user)
        resp = client.get('/dashboard.html')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # 50,000 @ 5% × min 1 day = 2,500 available balance.
        # The template applies intcomma, so it renders as 2,500.00.
        self.assertContains(resp, '2,500.00')

    def test_withdraw_page_renders_with_balance(self):
        client = Client()
        client.force_login(self.user)
        resp = client.get('/withdraw.html')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Available balance')

    def test_plans_page_renders(self):
        client = Client()
        client.force_login(self.user)
        resp = client.get('/plans.html')
        self.assertEqual(resp.status_code, 200)
        # Both plan cards must link to deposit with the plan pre-selected
        self.assertContains(resp, 'deposit.html?plan=')

    def test_deposit_page_preselects_plan(self):
        client = Client()
        client.force_login(self.user)
        resp = client.get(f'/deposit.html?plan={self.premium.id}')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # The chosen plan's <option> must be marked selected
        self.assertRegex(
            html,
            r'<option value="%s"[^>]*selected' % self.premium.id,
        )


@override_settings(
    PAYSTACK_SECRET_KEY='sk_test_webhook_secret',
    PAYSTACK_PUBLIC_KEY='pk_test_public',
    SITE_BASE_URL='https://example.com',
)
class PaystackWebhookTests(TestCase):
    """Server-to-server webhook: signature verification + auto wallet credit."""

    def setUp(self):
        self.user = User.objects.create_user('webhookuser', 'w@t.com', 'x12345678')
        self.plan = Plan.objects.create(
            name='Basic', price=Decimal('10000'), daily_percent=Decimal('3'),
            duration_days=30,
        )

    def _signed_payload(self, reference, event='charge.success', status='success'):
        payload = json.dumps({
            'event': event,
            'data': {'reference': reference, 'status': status, 'amount': 1000000},
        }).encode('utf-8')
        signature = hmac.new(
            b'sk_test_webhook_secret', payload, hashlib.sha512
        ).hexdigest()
        return payload, signature

    def test_signature_verification(self):
        body = b'{"event": "charge.success"}'
        good = hmac.new(b'sk_test_webhook_secret', body, hashlib.sha512).hexdigest()
        self.assertTrue(verify_paystack_webhook_signature(body, good))
        self.assertFalse(verify_paystack_webhook_signature(body, 'deadbeef'))
        self.assertFalse(verify_paystack_webhook_signature(body, ''))

    def test_webhook_rejects_unsigned_request(self):
        resp = self.client.post('/paystack/webhook', data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_webhook_credits_pending_deposit(self):
        dep = Deposit.objects.create(
            user=self.user, plan=self.plan, amount=Decimal('10000'),
            status='pending', paystack_ref='pw_webhooktest123',
        )
        body, signature = self._signed_payload(dep.paystack_ref)
        resp = self.client.post(
            '/paystack/webhook',
            data=body,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )
        self.assertEqual(resp.status_code, 200)
        dep.refresh_from_db()
        self.assertEqual(dep.status, 'approved')
        self.assertTrue(dep.verified)

    def test_webhook_does_not_double_credit(self):
        dep = Deposit.objects.create(
            user=self.user, plan=self.plan, amount=Decimal('10000'),
            status='approved', verified=True, paystack_ref='pw_webhooktest456',
        )
        body, signature = self._signed_payload(dep.paystack_ref)
        resp = self.client.post(
            '/paystack/webhook',
            data=body,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )
        self.assertEqual(resp.status_code, 200)
        # Still a single approved transaction
        self.assertEqual(dep.transactions.filter(status='approved').count(), 0)

    def test_url_builders(self):
        self.assertEqual(
            build_paystack_webhook_url(),
            'https://example.com/paystack/webhook',
        )
        self.assertEqual(
            build_paystack_callback_url(),
            'https://example.com/paystack/callback',
        )

    def test_webhook_pending_event_keeps_deposit_pending(self):
        """charge.pending → deposit stays pending, NOT rejected."""
        dep = Deposit.objects.create(
            user=self.user, plan=self.plan, amount=Decimal('10000'),
            status='pending', paystack_ref='pw_webhookpend1',
        )
        body, signature = self._signed_payload(
            dep.paystack_ref, event='charge.pending', status='pending',
        )
        resp = self.client.post(
            '/paystack/webhook',
            data=body,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )
        self.assertEqual(resp.status_code, 200)
        dep.refresh_from_db()
        self.assertEqual(dep.status, 'pending')
        self.assertFalse(dep.verified)

    def test_webhook_failed_event_marks_rejected(self):
        """charge.failed → pending deposit becomes rejected."""
        dep = Deposit.objects.create(
            user=self.user, plan=self.plan, amount=Decimal('10000'),
            status='pending', paystack_ref='pw_webhookfail1',
        )
        body, signature = self._signed_payload(
            dep.paystack_ref, event='charge.failed', status='failed',
        )
        resp = self.client.post(
            '/paystack/webhook',
            data=body,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )
        self.assertEqual(resp.status_code, 200)
        dep.refresh_from_db()
        self.assertEqual(dep.status, 'rejected')

    # ── Callback (browser redirect) 3-state routing ───────────────────
    def _mock_verify(self, status):
        return patch(
            'dashboard.views.verify_paystack_transaction',
            return_value={'status': status, 'reference': 'ref'},
        )

    def test_callback_success_redirects_to_success_page(self):
        dep = Deposit.objects.create(
            user=self.user, plan=self.plan, amount=Decimal('10000'),
            status='pending', paystack_ref='pw_cb_success',
        )
        with self._mock_verify('success'):
            resp = self.client.get(f'/paystack/callback?reference={dep.paystack_ref}')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('?paid=1', resp.url)
        dep.refresh_from_db()
        self.assertEqual(dep.status, 'approved')
        self.assertTrue(dep.verified)

    def test_callback_pending_redirects_to_pending_page(self):
        """Pending verification → pending page, deposit stays pending."""
        dep = Deposit.objects.create(
            user=self.user, plan=self.plan, amount=Decimal('10000'),
            status='pending', paystack_ref='pw_cb_pending',
        )
        with self._mock_verify('pending'):
            resp = self.client.get(f'/paystack/callback?reference={dep.paystack_ref}')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('?pending=1', resp.url)
        dep.refresh_from_db()
        self.assertEqual(dep.status, 'pending')
        self.assertFalse(dep.verified)

    def test_callback_failed_redirects_to_failed_page(self):
        """Abandoned/failed verification → failed page, deposit rejected."""
        dep = Deposit.objects.create(
            user=self.user, plan=self.plan, amount=Decimal('10000'),
            status='pending', paystack_ref='pw_cb_failed',
        )
        with self._mock_verify('abandoned'):
            resp = self.client.get(f'/paystack/callback?reference={dep.paystack_ref}')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('?failed=1', resp.url)
        dep.refresh_from_db()
        self.assertEqual(dep.status, 'rejected')

    def test_callback_api_unreachable_keeps_pending(self):
        """Paystack API down (verify returns None) → pending page, NOT failed."""
        dep = Deposit.objects.create(
            user=self.user, plan=self.plan, amount=Decimal('10000'),
            status='pending', paystack_ref='pw_cb_unreach',
        )
        with patch(
            'dashboard.views.verify_paystack_transaction',
            return_value=None,
        ):
            resp = self.client.get(f'/paystack/callback?reference={dep.paystack_ref}')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('?pending=1', resp.url)
        dep.refresh_from_db()
        self.assertEqual(dep.status, 'pending')
        self.assertFalse(dep.verified)

    def test_deposit_page_shows_pending_notice(self):
        client = Client()
        client.force_login(self.user)
        resp = client.get('/deposit.html?pending=1')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'payment is still being processed')

    def test_deposit_page_shows_failed_notice(self):
        client = Client()
        client.force_login(self.user)
        resp = client.get('/deposit.html?failed=1')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Payment failed')


class AdminPaymentsPageTests(TestCase):
    """The admin \"Payments\" page shows the URLs to add in the Paystack dashboard."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            'adminpay', 'ap@t.com', 'x12345678',
        )
        self.user = User.objects.create_user('plainuser', 'p@t.com', 'x12345678')

    def test_page_requires_staff(self):
        client = Client()
        client.force_login(self.user)
        resp = client.get('/adminpanel/payments')
        # Redirects to login — not accessible to normal users
        self.assertNotEqual(resp.status_code, 200)

    def test_page_shows_webhook_and_callback_urls(self):
        client = Client()
        client.force_login(self.admin)
        resp = client.get('/adminpanel/payments')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # URL builders use the root-level paths (/paystack/webhook, /paystack/callback)
        self.assertIn('paystack/webhook', html)
        self.assertIn('paystack/callback', html)
        self.assertIn('Webhook URL', html)
        self.assertIn('Redirect / Callback URL', html)
