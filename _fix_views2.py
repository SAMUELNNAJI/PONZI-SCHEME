#!/usr/bin/env python
"""Rewrite adminpanel/views.py."""
lines = []
A = lines.append

A('from decimal import Decimal, InvalidOperation')
A('from django.contrib.admin.views.decorators import staff_member_required')
A('from django.contrib.auth.models import User')
A('from django.db.models import Q, Sum')
A('from django.shortcuts import get_object_or_404, redirect, render')
A('from django.utils import timezone')
A('')
A('from adminpanel.models import SiteSetting, log_action')
A('from dashboard.models import (')
A('    Deposit, Notification, Plan, Transaction, Withdrawal,')
A(')')
A('from .models import ActivityLog')
A('')
A("admin_required = staff_member_required(login_url='/login.html')")
A('')
A('DEFAULT_PLANS = [')
for n, b, p, a in [
    ('Starter Plan', 'basic', 7000, False),
    ('Classy Plan', 'basic', 15000, False),
    ('Royal Plan', 'premium', 42000, False),
    ('Deluxe Plan', 'premium', 151000, False),
    ('Business Suit', 'popular', 250000, True),
    ('Empire Plan', 'premium', 451000, False),
    ('Platinum Plan', 'value', 720000, False),
    ('Gold Plan', 'hot', 1000000, False),
    ('Diamond Plan', 'diamond', 2500000, False),
    ('Premium Elite', 'vip', 5000000, True),
]:
    A(f"    ('{n}', '{b}', {p}, {a}),")
A(']')

open('_views_new.py', 'w', encoding='utf-8').write('\n'.join(lines))
print("Part 1 written to _views_new.py")
