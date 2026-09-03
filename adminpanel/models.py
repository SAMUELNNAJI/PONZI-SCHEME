from django.conf import settings
from django.db import models


class SiteSetting(models.Model):
    """Single-row table of editable platform settings."""

    site_name = models.CharField(max_length=100, default='Premium Wallet')
    support_email = models.EmailField(default='support@premiumwallet.com')
    min_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=7000)
    min_withdraw = models.DecimalField(max_digits=12, decimal_places=2, default=5000)

    class Meta:
        verbose_name = 'Site settings'
        verbose_name_plural = 'Site settings'

    def __str__(self):
        return 'Site settings'

    def save(self, *args, **kwargs):
        # Keep it a singleton — always pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ActivityLog(models.Model):
    """Audit trail: logins, submissions and admin actions."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
    )
    actor_name = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Activity logs'

    def __str__(self):
        return f"{self.actor_name}: {self.action}"


def log_action(actor, action):
    """Helper used across the apps to record an activity log entry."""
    return ActivityLog.objects.create(
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        actor_name=(actor.username if getattr(actor, 'is_authenticated', False)
                    and actor.username else str(actor) if actor else 'Anonymous'),
        action=action,
    )
