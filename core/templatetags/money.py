from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()

@register.filter
def brl(value):
    try:
        amount = Decimal(str(value if value is not None else 0))
        formatted = format(amount, ',.2f').replace(',', '_').replace('.', ',').replace('_', '.')
        return f'R$ {formatted}'
    except (InvalidOperation, TypeError, ValueError):
        return 'R$ 0,00'
