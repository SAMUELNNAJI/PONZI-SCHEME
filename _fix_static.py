import os

# Map of template files and their CSS/JS files
templates = {
    'templates/authentication/login.html': ['auth.css'],
    'templates/authentication/signup.html': ['auth.css'],
    'templates/dashboard/index.html': ['styles.css', 'main.js'],
    'templates/dashboard/dashboard.html': ['dashboard.css', 'main.js'],
    'templates/dashboard/plans.html': ['dashboard.css', 'main.js'],
    'templates/dashboard/deposit.html': ['dashboard.css', 'main.js'],
    'templates/dashboard/withdraw.html': ['dashboard.css', 'main.js'],
    'templates/dashboard/history.html': ['dashboard.css', 'main.js'],
    'templates/dashboard/referrals.html': ['dashboard.css', 'main.js'],
    'templates/dashboard/settings.html': ['dashboard.css', 'main.js'],
    'templates/adminpanel/base.html': ['dashboard.css'],
}

for path, files in templates.items():
    if not os.path.exists(path):
        print(f'SKIP: {path} not found')
        continue
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add {% load static %} after <!DOCTYPE html> if not present
    if '{% load static %}' not in content:
        content = content.replace('<!DOCTYPE html>', '{% load static %}\n<!DOCTYPE html>', 1)
    
    # Replace CSS links
    for f in files:
        # Build the replacement strings
        static_css = 'href="{% static \'' + f + '\' %}"'
        static_js = 'src="{% static \'' + f + '\' %}"'
        
        # Replace absolute path /file.css
        content = content.replace('href="/' + f + '"', static_css)
        # Replace relative path file.css
        content = content.replace('href="' + f + '"', static_css)
        # Replace JS
        content = content.replace('src="' + f + '"', static_js)
        content = content.replace('src="/' + f + '"', static_js)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'OK: {path}')