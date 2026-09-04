#!/usr/bin/env python
"""Fix adminpanel/views.py - part 1: fix broken plans function."""
import re

content = open('adminpanel/views.py', 'r', encoding='utf-8').read()

old_plans = """def plans(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        def imports(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'import':
            created = 0
            for order, (name, badge, price, accent) in enumerate(DEFAULT_PLANS):
                _, was_created = Plan.objects.get_or_create(
                    name=name,
                    defaults={'badge': badge, 'price': price, 'accent': accent,
                              'daily_percent': 3, 'duration_days': 30, 'sort_order': order},
                )
                created += int(was_created)
            log_action(request.user, f'Imported default plans ({created} new)')
        elif action == 'delete':
            plan = get_object_or_404(Plan, pk=request.POST.get('pk'))
            name = plan.name
            plan.delete()
            log_action(request.user, f'Deleted plan "{name}"')
        return redirect('adminpanel:plans')
    return render(request, 'adminpanel/plans.html', {
        'plans_list': Plan.objects.all(),
    })"""

new_plans = """def plans(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'import':
            created = 0
            for order, (name, badge, price, accent) in enumerate(DEFAULT_PLANS):
                _, was_created = Plan.objects.get_or_create(
                    name=name,
                    defaults={'badge': badge, 'price': price, 'accent': accent,
                              'daily_percent': 3, 'duration_days': 30, 'sort_order': order},
                )
                created += int(was_created)
            log_action(request.user, f'Imported default plans ({created} new)')
        elif action == 'delete':
            plan = get_object_or_404(Plan, pk=request.POST.get('pk'))
            name = plan.name
            plan.delete()
            log_action(request.user, f'Deleted plan "{name}"')
        return redirect('adminpanel:plans')

    return render(request, 'adminpanel/plans.html', {
        'plans_list': Plan.objects.all(),
    })"""

if old_plans in content:
    content = content.replace(old_plans, new_plans)
    print("Plans: FIXED")
else:
    print("Plans: NOT FOUND")

open('adminpanel/views.py', 'w', encoding='utf-8').write(content)
print("Saved part 1")
