from django.conf import settings
from django.db import models


class Profile(models.Model):
    """Extra account details beyond Django's built-in User."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    phone = models.CharField(max_length=20, blank=True)
    referral_code = models.CharField(max_length=20, blank=True, unique=True)
    referred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals',
        )
    referral_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Commission earned from referred users.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def referred_by_ref_code(self):
        """Return the referral_code of the user who referred this one (or '')."""
        if self.referred_by_id:
            try:
                return self.referred_by.profile.referral_code or ''
            except Profile.DoesNotExist:
                return ''
        return ''

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)

    @classmethod
    def generate_referral_code(cls):
        import secrets

        while True:
            code = 'PW-' + secrets.token_hex(4).upper()
            if not cls.objects.filter(referral_code=code).exists():
                return code

    def __str__(self):
        return f"Profile of {self.user.email or self.user.username}"
