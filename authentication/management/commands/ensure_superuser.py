"""
Creates a default superuser if none exists.

Set credentials via environment variables:
  - SUPERUSER_USERNAME (default: admin)
  - SUPERUSER_EMAIL (default: admin@premiumwallet.com)
  - SUPERUSER_PASSWORD (default: admin123)

Usage:
  python manage.py ensure_superuser
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
import os


class Command(BaseCommand):
    help = 'Create a superuser if none exists'

    def handle(self, *args, **options):
        username = os.environ.get('SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('SUPERUSER_EMAIL', 'admin@premiumwallet.com')
        password = os.environ.get('SUPERUSER_PASSWORD', 'admin123')

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
            )
            self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" created.'))
        else:
            self.stdout.write(self.style.WARNING(f'Superuser "{username}" already exists.'))