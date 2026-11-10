"""Transactional commands for stock, settlements, and payments.

Quantities passed to settle_item are increments, never replacement totals.
Money stays Decimal end to end. All commands reload persisted state under a lock.
"""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Consignment, ConsignmentItem, Payment, Product, StockMovement


def _integer(value, label, *, allow_negative=False):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f'{label} deve ser um número inteiro.')
    if not allow_negative and value < 0:
        raise ValidationError(f'{label} não pode ser negativa.')
    return value


def _money(value):
    if isinstance(value, (float, bool)):
        raise ValidationError('Informe o valor monetário com até duas casas decimais.')
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount.as_tuple().exponent < -2:
            raise InvalidOperation
        return amount
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError('Informe um valor monetário válido com até duas casas decimais.')


def _require_status(consignment, status):
    if consignment.status != status:
        labels = dict(Consignment.Status.choices)
        raise ValidationError(f'Esta operação exige uma consignação com situação: {labels[status].lower()}.')


@transaction.atomic
def send_consignment(consignment):
    current = Consignment.objects.select_for_update().select_related('client').get(pk=consignment.pk)
    _require_status(current, Consignment.Status.DRAFT)
    if not current.client.active:
        raise ValidationError('Ative a cliente antes de enviar uma consignação.')
    current.full_clean()
    items = list(current.items.select_for_update().order_by('product_id'))
    if not items:
        raise ValidationError('Inclua ao menos um produto antes de enviar a consignação.')
    products = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=[i.product_id for i in items]).order_by('pk')}
    for reference in current.consignmentcontact_set.select_related('contact'):
        reference.full_clean()
    for item in items:
        item.full_clean()
        product = products[item.product_id]
        if not product.active:
            raise ValidationError(f'O produto {product.name} está inativo.')
        if product.stock_quantity < item.quantity:
            raise ValidationError(f'Estoque insuficiente de {product.name}: disponível {product.stock_quantity}, solicitado {item.quantity}.')
    for item in items:
        product = products[item.product_id]
        item.product_name = product.name
        item.product_sku = product.sku
        item.unit_cost = product.total_cost
        item.save(update_fields=['product_name', 'product_sku', 'unit_cost'])
        product.stock_quantity -= item.quantity
        product.save(update_fields=['stock_quantity', 'updated_at'])
        StockMovement.objects.create(product=product, consignment=current, kind=StockMovement.Kind.OUT,
                                     quantity=-item.quantity, note=f'Envio {current.code}')
    current.status = Consignment.Status.SENT
    current.save(update_fields=['status', 'updated_at'])
    consignment.refresh_from_db()
    return consignment


@transaction.atomic
def settle_item(item, sold=0, returned=0):
    sold = _integer(sold, 'A quantidade vendida')
    returned = _integer(returned, 'A quantidade devolvida')
    if sold + returned == 0:
        raise ValidationError('Informe ao menos uma venda ou devolução.')
    current = Consignment.objects.select_for_update().get(pk=item.consignment_id)
    _require_status(current, Consignment.Status.SENT)
    current_item = ConsignmentItem.objects.select_for_update().get(pk=item.pk, consignment=current)
    if sold + returned > current_item.pending_quantity:
        raise ValidationError(f'Existem somente {current_item.pending_quantity} unidades pendentes deste produto.')
    current_item.sold_quantity += sold
    current_item.returned_quantity += returned
    current_item.save(update_fields=['sold_quantity', 'returned_quantity'])
    if returned:
        product = Product.objects.select_for_update().get(pk=current_item.product_id)
        product.stock_quantity += returned
        product.save(update_fields=['stock_quantity', 'updated_at'])
        StockMovement.objects.create(product=product, consignment=current, kind=StockMovement.Kind.RETURN,
                                     quantity=returned, note=f'Devolução {current.code}')
    item.refresh_from_db()
    return item


@transaction.atomic
def add_payment(consignment, amount, paid_date, method, notes=''):
    current = Consignment.objects.select_for_update().get(pk=consignment.pk)
    _require_status(current, Consignment.Status.SENT)
    amount = _money(amount)
    if amount <= 0:
        raise ValidationError('O pagamento deve ser maior que zero.')
    if amount > current.balance:
        raise ValidationError('O pagamento excede o saldo das vendas registradas.')
    payment = Payment(consignment=current, amount=amount, paid_date=paid_date, method=method, notes=notes)
    payment.save()
    consignment.refresh_from_db()
    return payment


@transaction.atomic
def close_consignment(consignment):
    current = Consignment.objects.select_for_update().get(pk=consignment.pk)
    _require_status(current, Consignment.Status.SENT)
    if current.pending_quantity:
        raise ValidationError('Registre a venda ou devolução de todas as peças antes de encerrar.')
    if current.balance != 0:
        raise ValidationError('Registre o pagamento do saldo pendente antes de encerrar.')
    current.status = Consignment.Status.CLOSED
    current.save(update_fields=['status', 'updated_at'])
    consignment.refresh_from_db()
    return consignment


@transaction.atomic
def cancel_consignment(consignment):
    current = Consignment.objects.select_for_update().get(pk=consignment.pk)
    _require_status(current, Consignment.Status.DRAFT)
    current.status = Consignment.Status.CANCELLED
    current.save(update_fields=['status', 'updated_at'])
    consignment.refresh_from_db()
    return consignment


@transaction.atomic
def adjust_stock(product, quantity, note):
    quantity = _integer(quantity, 'A quantidade', allow_negative=True)
    if not quantity:
        raise ValidationError('Informe uma quantidade diferente de zero.')
    if not str(note).strip():
        raise ValidationError('Descreva o motivo da movimentação de estoque.')
    current = Product.objects.select_for_update().get(pk=product.pk)
    if current.stock_quantity + quantity < 0:
        raise ValidationError('O ajuste não pode deixar o estoque negativo.')
    current.stock_quantity += quantity
    current.save(update_fields=['stock_quantity', 'updated_at'])
    movement = StockMovement.objects.create(product=current, kind=StockMovement.Kind.ADJUSTMENT,
                                           quantity=quantity, note=note)
    product.refresh_from_db()
    return movement
