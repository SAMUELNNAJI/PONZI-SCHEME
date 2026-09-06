"""
Data migration: ensure every Profile has a unique referral code.
Runs automatically as part of `manage.py migrate`.
"""
from django.db import migrations


def backfill_codes(apps, schema_editor):
    Profile = apps.get_model('authentication', 'Profile')
    import secrets

    for profile in Profile.objects.filter(referral_code=''):
        while True:
            code = 'PW-' + secrets.token_hex(4).upper()
            if not Profile.objects.filter(referral_code=code).exists():
                break
        profile.referral_code = code
        profile.save(update_fields=['referral_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0003_profile_preferences'),
    ]

    operations = [
        migrations.RunPython(backfill_codes, reverse_code=migrations.RunPython.noop),
    ]
