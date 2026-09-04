#!/usr/bin/env bash
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Apply database migrations
python manage.py migrate --no-input

# Create superuser if it doesn't exist (optional, for first deploy)
# python manage.py createsuperuser --noinput --username admin --email admin@example.com || true