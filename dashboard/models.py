from django.conf import settings
from django.db import models


class Plan(models.Model):
    """An investment plan (seeded from the site's 10 plans)."""

    BADGES = [
        ('basic', 'Basic'),
        ('premium', 'Premium'),
        ('popular', 'Most Popular'),
        ('value', 'Best Value'),
        ('hot', '🔥 Hot'),
        ('diamond', 'Diamond'),
        ('vip', 'VIP'),
        ]

    name = models.CharField(max_length=100)
    badge = models.CharField(max_length=20, choices=BADGES, default='basic')
    accent = models.BooleanField(
        default=False, help_text='Highlight the plan name in blue'
    )
    # --- Custom badge display (overridden on the card) ---
    badge_text = models.CharField(
        max_length=40, blank=True,
        help_text='Custom badge label, e.g. "Best Value". Leave blank to use the default badge.',
    )
    badge_gradient_from = models.CharField(
        max_length=7, default='#FF6B6B',
        help_text='Hex color for the badge gradient start, e.g. #FF6B6B',
    )
    badge_gradient_to = models.CharField(
        max_length=7, default='#F7971E',
        help_text='Hex color for the badge gradient end, e.g. #F7971E',
    )
    daily_percent = models.DecimalField(max_digits=5, decimal_places=2, default=3)
    duration_days = models.PositiveIntegerField(default=30)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'price']

    def __str__(self):
        return self.name

    @property
    def daily_profit(self):
        return self.price * self.daily_percent / 100

    @property
    def total_payout(self):
        return self.price + self.daily_profit * self.duration_days


class Deposit(models.Model):
    """A deposit submitted by a user, awaiting admin confirmation."""

    STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    METHODS = [
        ('bank', 'Bank Transfer'),
        ('usdt', 'USDT TRC20'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deposits'
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.SET_NULL, null=True, blank=True, related_name='deposits'
        )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHODS, default='bank')
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    # --- Paystack integration ---
    paystack_ref = models.CharField(
        max_length=191, blank=True,
        help_text='Paystack transaction reference (for verification).',
    )
    verified = models.BooleanField(
        default=False,
        help_text='Set True after Paystack callback verifies the payment.',
    )
    admin_confirmed = models.BooleanField(
        default=False,
        help_text='Set True manually if you credit the wallet by hand (dev fallback).',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Deposit ₦{self.amount:,.0f} by {self.user.username} ({self.status})"


class Withdrawal(models.Model):
    """A withdrawal request submitted by a user, awaiting admin approval."""

    STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    METHODS = [
        ('bank', 'Bank Transfer'),
        ('usdt', 'USDT TRC20'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withdrawals'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHODS, default='bank')
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=20, blank=True)
    account_name = models.CharField(max_length=100, blank=True)
    usdt_address = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    requested_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When the user submitted the request (for once-per-day limit).',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    paid = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Withdrawal ₦{self.amount:,.0f} by {self.user.username} ({self.status})"


class Transaction(models.Model):
    """Unified record of every deposit/withdrawal on the platform."""

    TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('referral', 'Referral Credit'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions'
    )
    tx_type = models.CharField(max_length=12, choices=TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, default='pending')
    deposit = models.ForeignKey(
        Deposit, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions'
    )
    withdrawal = models.ForeignKey(
        Withdrawal, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tx_type.title()} ₦{self.amount:,.0f} — {self.user.username}"


class Notification(models.Model):
    """Admin-created announcement shown on every user dashboard."""

    title = models.CharField(max_length=120)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    email_sent = models.BooleanField(
        default=False,
        help_text='Mark True after emailing the notification to all users.',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title