"""Seed the database with the site's 10 investment plans (idempotent)."""
from django.core.management.base import BaseCommand

from dashboard.models import Plan

DEFAULT_PLANS = [
    ('Starter Plan',   'basic',   7000,     False),
    ('Classy Plan',    'basic',   15000,    False),
    ('Royal Plan',     'premium', 42000,    False),
    ('Deluxe Plan',    'premium', 151000,   False),
    ('Business Suit',  'popular', 250000,   True),
    ('Empire Plan',    'premium', 451000,   False),
    ('Platinum Plan',  'value',   720000,   False),
    ('Gold Plan',      'hot',     1000000,  False),
    ('Diamond Plan',   'diamond', 2500000,  False),
    ('Premium Elite',  'vip',     5000000,  True),
]


class Command(BaseCommand):
    help = 'Create the 10 default investment plans if they do not exist.'

    def handle(self, *args, **options):
        created = 0
        for order, (name, badge, price, accent) in enumerate(DEFAULT_PLANS):
            plan, was_created = Plan.objects.get_or_create(
                name=name,
                defaults={
                    'badge': badge,
                    'price': price,
                    'accent': accent,
                    'daily_percent': 3,
                    'duration_days': 30,
                    'sort_order': order,
                },
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {created} plan(s); {Plan.objects.count()} plan(s) in total.'
        ))
