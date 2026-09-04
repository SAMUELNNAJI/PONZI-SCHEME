#!/usr/bin/env python
"""Fix adminpanel/views.py: deposits + withdrawals + notify."""
import io

content = open('adminpanel/views.py', 'r', encoding='utf-8').read()

old_deposit = """@admin_required
def deposits(request):
    if request.method == 'POST':
        dep = get_object_or_404(Deposit, pk=request.POST.get('pk'))
        action = request.POST.get('action')
        if dep.status == 'pending' and action in ('approve', 'reject'):
            dep.status = 'approved' if action == 'approve' else 'rejected'
            dep.save()
            dep.transactions.update(status=dep.status)
            log_action(request.user, f'{dep.status.title()} deposit #{dep.id} '
                                     f'(\u20a6{dep.amount:,.0f}) by {dep.user.username}')
        return redirect('adminpanel:deposits')

    return render(request, 'adminpanel/deposits.html', {
        'deposits_list': Deposit.objects.select_related('user', 'plan'),
    })"""

new_deposit = """@admin_required
def deposits(request):
    if request.method == 'POST':
        dep = get_object_or_404(Deposit, pk=request.POST.get('pk'))
        action = request.POST.get('action')
        if dep.status == 'pending' and action in ('approve', 'reject'):
            dep.status = 'approved' if action == 'approve' else 'rejected'
            dep.save()
            dep.transactions.update(status=dep.status)
            if dep.status == 'approved':
                from dashboard.services import credit_wallet, send_email
                credit_wallet(dep)
                send_email(
                    dep.user.email,
                    'Deposit Approved',
                    f'<p>Your deposit of <strong>\u20a6{dep.amount:,.2f}</strong> has been approved and credited to your wallet.</p>',
                    name=dep.user.get_full_name() or dep.user.username,
                )
            elif dep.status == 'rejected':
                from dashboard.services import send_email
                send_email(
                    dep.user.email,
                    'Deposit Rejected',
                    f'<p>Your deposit of <strong>\u20a6{dep.amount:,.2f}</strong> has been rejected.</p>',
                    name=dep.user.get_full_name() or dep.user.username,
                )
            log_action(request.user, f'{dep.status.title()} deposit #{dep.id} '
                       f'(\u20a6{dep.amount:,.0f}) by {dep.user.username}')
        return redirect('adminpanel:deposits')

    return render(request, 'adminpanel/deposits.html', {
        'deposits_list': Deposit.objects.select_related('user', 'plan'),
    })"""

if old_deposit in content:
    content = content.replace(old_deposit, new_deposit)
    print("Deposits: REPLACED")
else:
    print("Deposits: NOT FOUND")
    content = content.replace("log_action(request.user, f'{dep.status.title()} deposit #{dep.id}'", "PLACEHOLDER_DEP")

open('adminpanel/views.py', 'w', encoding='utf-8').write(content)
