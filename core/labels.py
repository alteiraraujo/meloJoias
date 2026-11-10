"""EAN-13 labels for restricted, internal circulation (not registered GTINs)."""
from secrets import randbelow

from barcode import EAN13
from django.core.exceptions import ValidationError


def validate_ean13(value):
    if len(value) != 13 or not value.isascii() or not value.isdigit():
        raise ValidationError('O EAN deve conter exatamente 13 dígitos.')
    if EAN13(value[:12]).get_fullcode() != value:
        raise ValidationError('Dígito verificador do EAN inválido.')


def generate_internal_ean():
    from .models import Product
    for _ in range(100):
        value = EAN13(f'20{randbelow(10**10):010d}').get_fullcode()
        if not Product.objects.filter(ean13=value).exists() and not Product.objects.filter(sku=value).exists():
            return value
    raise ValidationError('Não foi possível gerar um código livre. Tente salvar novamente.')
