from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from .labels import generate_internal_ean, validate_ean13
from .addresses import STATES, validate_postal_code, address_lines, address_missing, postal_code_display


ZERO = Decimal('0.00')
MONEY_VALIDATORS = [MinValueValidator(ZERO)]


class ValidatedModel(models.Model):
    """Keep ORM writes subject to the same validation as the forms."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Category(ValidatedModel):
    name = models.CharField('nome', max_length=100, unique=True)
    description = models.TextField('descrição', blank=True)
    active = models.BooleanField('ativa', default=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'categoria'

    def __str__(self):
        return self.name


class Product(ValidatedModel):
    sku = models.CharField('código', max_length=40, unique=True)
    ean13 = models.CharField('EAN-13 interno', max_length=13, unique=True, editable=False,
                             validators=[validate_ean13])
    name = models.CharField('nome', max_length=160)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name='categoria')
    description = models.TextField('descrição', blank=True)
    sale_price = models.DecimalField('preço de venda', max_digits=12, decimal_places=2, validators=MONEY_VALIDATORS)
    photo = models.ImageField('foto do produto', upload_to='products/', blank=True)
    stock_quantity = models.PositiveIntegerField('estoque disponível', default=0)
    minimum_stock = models.PositiveIntegerField('estoque mínimo', default=3)
    active = models.BooleanField('ativo', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'produto'
        constraints = [
            models.CheckConstraint(condition=Q(sale_price__gte=0), name='product_price_nonnegative'),
            models.CheckConstraint(condition=Q(stock_quantity__gte=0), name='product_stock_nonnegative'),
            models.CheckConstraint(condition=Q(minimum_stock__gte=0), name='product_minimum_nonnegative'),
        ]

    def __str__(self):
        return f'{self.sku} · {self.name}'

    def save(self, *args, **kwargs):
        if not self.ean13:
            self.ean13 = generate_internal_ean()
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'ean13'}
        return super().save(*args, **kwargs)

    @property
    def total_cost(self):
        return sum((cost.amount for cost in self.costs.all()), ZERO) if self.pk else ZERO

    @property
    def stock_value(self):
        return self.stock_quantity * self.sale_price


class CostType(ValidatedModel):
    name = models.CharField('nome', max_length=100, unique=True)
    description = models.TextField('descrição', blank=True)
    active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'tipo de custo'

    def __str__(self):
        return self.name


class ProductCost(ValidatedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='costs', verbose_name='produto')
    cost_type = models.ForeignKey(CostType, on_delete=models.PROTECT, verbose_name='tipo de custo')
    description = models.CharField('descrição', max_length=200, blank=True)
    amount = models.DecimalField('custo por unidade', max_digits=12, decimal_places=2, validators=MONEY_VALIDATORS)

    class Meta:
        ordering = ['cost_type__name', 'pk']
        verbose_name = 'custo do produto'
        constraints = [models.CheckConstraint(condition=Q(amount__gte=0), name='product_cost_nonnegative')]

    def __str__(self):
        return f'{self.product.name} · {self.cost_type.name}'


class PostalAddress(ValidatedModel):
    postal_code = models.CharField('CEP', max_length=9, blank=True, validators=[validate_postal_code])
    street = models.CharField('logradouro', max_length=100, blank=True)
    number = models.CharField('número', max_length=15, blank=True)
    complement = models.CharField('complemento', max_length=80, blank=True)
    neighborhood = models.CharField('bairro', max_length=80, blank=True)
    city = models.CharField('cidade', max_length=80, blank=True)
    state = models.CharField('UF', max_length=2, blank=True, choices=STATES)

    class Meta:
        abstract = True

    @property
    def postal_code_display(self):
        return postal_code_display(self.postal_code)


class SenderProfile(PostalAddress):
    name = models.CharField('nome / empresa do remetente', max_length=160, default='Melo Joias')
    phone = models.CharField('telefone', max_length=30, blank=True)

    class Meta:
        verbose_name = 'remetente'


class Client(PostalAddress):
    name = models.CharField('nome', max_length=160)
    document = models.CharField('CPF / CNPJ', max_length=25, blank=True)
    phone = models.CharField('telefone', max_length=30, blank=True)
    email = models.EmailField('e-mail', blank=True)
    address = models.TextField('endereço', blank=True)
    notes = models.TextField('observações', blank=True)
    active = models.BooleanField('ativa', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'revendedora'

    def __str__(self):
        return self.name

    @property
    def mailing_address(self):
        return address_lines(self) if not address_missing(self) else self.address


class Contact(ValidatedModel):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='contacts', verbose_name='revendedora')
    name = models.CharField('nome', max_length=160)
    relationship = models.CharField('vínculo / referência', max_length=100, blank=True)
    phone = models.CharField('telefone', max_length=30, blank=True)
    email = models.EmailField('e-mail', blank=True)
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'referência'

    def __str__(self):
        return f'{self.name} ({self.client.name})'

    def clean(self):
        super().clean()
        if self.pk and self.client_id and self.consignmentcontact_set.exclude(consignment__client_id=self.client_id).exists():
            raise ValidationError({'client': 'Esta referência está vinculada a uma consignação de outra revendedora.'})


class Consignment(ValidatedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'AGUARDANDO ENVIO'
        SENT = 'sent', 'EM TRÂNSITO'
        CLOSED = 'closed', 'FINALIZADO'
        CANCELLED = 'cancelled', 'Cancelada'

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='consignments', verbose_name='revendedora')
    sent_date = models.DateField('data de envio', default=timezone.localdate)
    tracking_code = models.CharField('código de rastreio', max_length=80, blank=True)
    shipping_responsible = models.CharField('responsável pelo envio', max_length=160, blank=True)
    shipping_method = models.CharField('tipo de envio', max_length=80, blank=True)
    signed_document = models.FileField('romaneio assinado', upload_to='signed-documents/', blank=True)
    signed_document_uploaded_at = models.DateTimeField('data do upload do romaneio', null=True, blank=True)
    due_date = models.DateField('data de acerto')
    notes = models.TextField('observações', blank=True)
    status = models.CharField('situação', max_length=12, choices=Status.choices, default=Status.DRAFT)
    contacts = models.ManyToManyField(Contact, through='ConsignmentContact', blank=True, verbose_name='referências')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = 'consignação'
        verbose_name_plural = 'consignações'
        constraints = [models.CheckConstraint(condition=Q(due_date__gte=F('sent_date')), name='consignment_dates_ordered')]
        indexes = [models.Index(fields=['status', 'due_date'], name='consignment_status_due')]

    def __str__(self):
        return f'{self.code} · {self.client.name}'

    def clean(self):
        super().clean()
        if self.sent_date and self.due_date and self.due_date < self.sent_date:
            raise ValidationError({'due_date': 'A data de acerto não pode ser anterior ao envio.'})
        # Draft forms replace reference contacts in the same transaction after
        # saving the client. Validate their selected contacts in the form and
        # revalidate every saved reference before shipping.
        if self.pk and self.status != self.Status.DRAFT and self.client_id and self.consignmentcontact_set.exclude(contact__client_id=self.client_id).exists():
            raise ValidationError({'client': 'As referências devem pertencer à revendedora selecionada.'})

    @property
    def code(self):
        return f'MJ-{self.pk:04d}' if self.pk else 'Nova consignação'

    @property
    def total_value(self):
        return sum((item.total_value for item in self.items.all()), ZERO) if self.pk else ZERO

    @property
    def sold_value(self):
        return sum((item.sold_quantity * item.unit_price for item in self.items.all()), ZERO) if self.pk else ZERO

    @property
    def paid_value(self):
        return sum((payment.amount for payment in self.payments.all()), ZERO) if self.pk else ZERO

    @property
    def balance(self):
        return self.sold_value - self.paid_value

    @property
    def pending_quantity(self):
        return sum(item.pending_quantity for item in self.items.all()) if self.pk else 0

    @property
    def is_overdue(self):
        return self.status == self.Status.SENT and self.due_date < timezone.localdate()


class ConsignmentContact(ValidatedModel):
    consignment = models.ForeignKey(Consignment, on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['consignment', 'contact'], name='unique_consignment_contact')]

    def clean(self):
        super().clean()
        if self.consignment_id and self.contact_id and self.consignment.client_id != self.contact.client_id:
            raise ValidationError({'contact': 'A referência deve pertencer à revendedora da consignação.'})


class ConsignmentItem(ValidatedModel):
    consignment = models.ForeignKey(Consignment, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='produto')
    quantity = models.PositiveIntegerField('quantidade enviada', validators=[MinValueValidator(1)])
    unit_price = models.DecimalField('preço por unidade', max_digits=12, decimal_places=2, validators=MONEY_VALIDATORS)
    sold_quantity = models.PositiveIntegerField('vendidas', default=0)
    returned_quantity = models.PositiveIntegerField('devolvidas', default=0)
    product_name = models.CharField('nome no envio', max_length=160, blank=True)
    product_sku = models.CharField('código no envio', max_length=40, blank=True)
    unit_cost = models.DecimalField('custo por unidade no envio', max_digits=12, decimal_places=2, default=ZERO, validators=MONEY_VALIDATORS)

    class Meta:
        ordering = ['pk']
        constraints = [
            models.UniqueConstraint(fields=['consignment', 'product'], name='unique_consignment_product'),
            models.CheckConstraint(condition=Q(quantity__gt=0), name='item_quantity_positive'),
            models.CheckConstraint(condition=Q(unit_price__gte=0) & Q(unit_cost__gte=0), name='item_prices_nonnegative'),
            models.CheckConstraint(condition=Q(sold_quantity__gte=0) & Q(returned_quantity__gte=0), name='item_settlement_nonnegative'),
            models.CheckConstraint(condition=Q(quantity__gte=F('sold_quantity') + F('returned_quantity')), name='item_settlement_within_quantity'),
        ]

    def clean(self):
        super().clean()
        if self.quantity is not None and (self.sold_quantity or 0) + (self.returned_quantity or 0) > self.quantity:
            raise ValidationError('A soma de vendas e devoluções não pode exceder a quantidade enviada.')
        if self.consignment_id and self.consignment.status == Consignment.Status.DRAFT and (self.sold_quantity or self.returned_quantity):
            raise ValidationError('Envie a consignação antes de registrar vendas ou devoluções.')
        if self.consignment_id and self.consignment.status != Consignment.Status.DRAFT:
            previous = type(self).objects.filter(pk=self.pk).first() if self.pk else None
            if not previous:
                raise ValidationError('Só é possível incluir produtos em consignações aguardando envio.')
            historical = ['consignment_id', 'product_id', 'quantity', 'unit_price', 'product_name', 'product_sku', 'unit_cost']
            if any(getattr(self, field) != getattr(previous, field) for field in historical):
                raise ValidationError('Os dados dos produtos enviados são históricos e não podem ser alterados.')

    @property
    def pending_quantity(self):
        return self.quantity - self.sold_quantity - self.returned_quantity

    @property
    def total_value(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f'{self.product_name or self.product.name} × {self.quantity}'


class Payment(ValidatedModel):
    class Method(models.TextChoices):
        PIX = 'pix', 'Pix'
        CASH = 'cash', 'Dinheiro'
        CARD = 'card', 'Cartão'
        TRANSFER = 'transfer', 'Transferência'
        OTHER = 'other', 'Outro'

    consignment = models.ForeignKey(Consignment, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField('valor', max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    paid_date = models.DateField('data do pagamento', default=timezone.localdate)
    method = models.CharField('forma de pagamento', max_length=12, choices=Method.choices, default=Method.PIX)
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['-paid_date', '-pk']
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name='payment_positive')]

    def clean(self):
        super().clean()
        if self.consignment_id:
            if self.consignment.status != Consignment.Status.SENT:
                raise ValidationError('Pagamentos só podem ser registrados em consignações em trânsito.')
            if self.amount is not None:
                already_paid = sum((p.amount for p in self.consignment.payments.exclude(pk=self.pk)), ZERO)
                if already_paid + self.amount > self.consignment.sold_value:
                    raise ValidationError({'amount': 'O pagamento excede o saldo das vendas registradas.'})


class StockMovement(ValidatedModel):
    class Kind(models.TextChoices):
        IN = 'in', 'Entrada'
        OUT = 'out', 'Envio em consignação'
        RETURN = 'return', 'Devolução'
        ADJUSTMENT = 'adjustment', 'Ajuste'

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_movements')
    consignment = models.ForeignKey(Consignment, on_delete=models.PROTECT, null=True, blank=True)
    kind = models.CharField('tipo', max_length=12, choices=Kind.choices)
    quantity = models.IntegerField('quantidade')
    note = models.CharField('observação', max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [
            models.CheckConstraint(condition=~Q(quantity=0), name='stock_movement_nonzero'),
            models.CheckConstraint(condition=(Q(kind__in=['in', 'return'], quantity__gt=0) | Q(kind='out', quantity__lt=0) | Q(kind='adjustment')), name='stock_movement_sign'),
        ]

    def clean(self):
        super().clean()
        if self.quantity == 0:
            raise ValidationError({'quantity': 'A movimentação deve ter quantidade diferente de zero.'})
        if self.quantity is not None:
            if self.kind in [self.Kind.IN, self.Kind.RETURN] and self.quantity < 0:
                raise ValidationError({'quantity': 'Entradas e devoluções devem ser positivas.'})
            if self.kind == self.Kind.OUT and self.quantity > 0:
                raise ValidationError({'quantity': 'O envio deve registrar uma saída negativa.'})
