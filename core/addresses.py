import re

from django.core.exceptions import ValidationError

STATES = [(uf, uf) for uf in 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split()]
ADDRESS_FIELDS = ['postal_code', 'street', 'number', 'complement', 'neighborhood', 'city', 'state']
REQUIRED_ADDRESS_FIELDS = ['postal_code', 'street', 'number', 'neighborhood', 'city', 'state']


def validate_postal_code(value):
    if not re.fullmatch(r'[0-9]{5}-?[0-9]{3}', value):
        raise ValidationError('Informe um CEP com 8 dígitos, por exemplo 01001-000.')


def postal_code_display(value):
    digits = value.replace('-', '')
    return f'{digits[:5]}-{digits[5:]}' if len(digits) == 8 else value


def address_missing(person):
    return [person._meta.get_field(field).verbose_name for field in REQUIRED_ADDRESS_FIELDS
            if not str(getattr(person, field, '') or '').strip()]


def address_lines(person):
    lines = [f'{person.street}, {person.number}', person.complement, person.neighborhood,
             f'{person.city} - {person.state}', f'CEP {postal_code_display(person.postal_code)}']
    return '\n'.join(line for line in lines if line)
