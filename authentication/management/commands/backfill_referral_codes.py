"""
Management command: backfill_referral_codes

Assigns a unique referral code to every Profile that currently has a blank one.
Safe to run multiple times — only touches profiles without a code.

Usage:
    python manage.py backfill_referral_codes
"""
from django.core.management.base import BaseCommand

from authentication.models import Profile


class Command(BaseCommand):
    help = 'Assign unique referral codes to profiles that are missing one.'

    def handle(self, *args, **options):
        blank = Profile.objects.filter(referral_code='')
        count = blank.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('All profiles already have a referral code.'))
            return

        fixed = 0
        for profile in blank:
            profile.referral_code = Profile.generate_referral_code()
            profile.save(update_fields=['referral_code'])
            fixed += 1
            self.stdout.write(f'  {profile.user.username} → {profile.referral_code}')

        self.stdout.write(self.style.SUCCESS(f'Fixed {fixed} profile(s).'))
