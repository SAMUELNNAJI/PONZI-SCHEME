from decimal import Decimal, InvalidOperation

from django import template
from django.contrib.humanize.templatetags.humanize import intcomma

register = template.Library()


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')


@register.simple_tag
def display_amount(value, currency, usd_rate):
    """
    Render a monetary value with the correct symbol and conversion.

    Usage in templates:
        {% display_amount stats.balance user_currency usd_rate %}

    - currency == 'NGN'  →  ₦1,234.56
    - currency == 'USD'  →  $7.71  (value / usd_rate, 2 d.p.)
    """
    amount = _to_decimal(value)
    rate = _to_decimal(usd_rate)

    if currency == 'USD' and rate > 0:
        converted = (amount / rate).quantize(Decimal('0.01'))
        return f'${intcomma(converted)}'

    # Default: NGN
    formatted = amount.quantize(Decimal('0.01'))
    return f'₦{intcomma(formatted)}'


@register.simple_tag
def currency_symbol(currency):
    """Return just the symbol: $ or ₦."""
    return '$' if currency == 'USD' else '₦'
