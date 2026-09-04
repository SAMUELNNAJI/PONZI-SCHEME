#!/usr/bin/env python
"""Fix the mangled Notification docstring."""
lines = open('dashboard/models.py', 'r', encoding='utf-8').read().splitlines()
lines[170] = '    """Admin-created announcement shown on every user dashboard."""'
open('dashboard/models.py', 'w', encoding='utf-8').write('\n'.join(lines))
print("Fixed line 171")
