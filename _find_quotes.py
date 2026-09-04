#!/usr/bin/env python
"""Find all triple quote lines in dashboard/models.py."""
lines = open('dashboard/models.py', 'r', encoding='utf-8').read().splitlines()
for i, l in enumerate(lines, 1):
    if '"""' in l:
        print(f'{i:3}| {l}')
