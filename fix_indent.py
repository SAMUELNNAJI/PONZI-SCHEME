with open(r'dashboard\views.py', 'r') as f:
    lines = f.readlines()

# Fix line 85 (index 84): "        # Build referral link" -> "    # Build referral link"
lines[84] = '    # Build referral link\n'

with open(r'dashboard\views.py', 'w') as f:
    f.writelines(lines)

print('Fixed comment indentation')
# Verify
for i in range(83, 87):
    print(f'Line {i+1}: {repr(lines[i].rstrip())}')