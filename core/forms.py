from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone
from .models import (Category, Product, CostType, ProductCost, Client, Contact,
                     Consignment, ConsignmentItem, Payment)


LABELS = {
    'name': 'Nome', 'description': 'Descrição', 'active': 'Ativo', 'sku': 'Código / SKU',
    'category': 'Categoria', 'sale_price': 'Preço de venda (R$)', 'minimum_stock': 'Estoque mínimo',
    'product': 'Produto', 'cost_type': 'Tipo de custo', 'amount': 'Valor (R$)',
    'client': 'Cliente', 'document': 'CPF / CNPJ', 'phone': 'Telefone / WhatsApp',
    'email': 'E-mail', 'address': 'Endereço', 'notes': 'Observações', 'relationship': 'Vínculo / referência',
    'sent_date': 'Data de envio', 'due_date': 'Prazo de acerto', 'contacts': 'Contatos de referência',
    'quantity': 'Quantidade', 'unit_price': 'Preço unitário (R$)', 'paid_date': 'Data do recebimento',
    'method': 'Forma de pagamento',
}


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.label = LABELS.get(name, field.label)
            field.widget.attrs.setdefault('class', 'form-control')
            if isinstance(field, forms.DecimalField):
                field.localize = True
                field.widget = forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'decimal', 'placeholder': '0,00'})
                field.widget.is_localized = True
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['rows'] = 3
            if isinstance(field, forms.DateField):
                field.widget = forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'})


class CategoryForm(StyledModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'active']


class ProductForm(StyledModelForm):
    initial_stock = forms.IntegerField(label='Estoque inicial', min_value=0, initial=0, required=False,
                                      help_text='Peças disponíveis para o primeiro envio.')
    class Meta:
        model = Product
        fields = ['sku', 'name', 'category', 'sale_price', 'minimum_stock', 'description', 'active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sku'].help_text = 'O leitor aceita este SKU ou o EAN-13 gerado automaticamente para a etiqueta.'
        if self.instance.pk:
            del self.fields['initial_stock']
        else:
            self.fields['category'].queryset = Category.objects.filter(active=True)


class CostTypeForm(StyledModelForm):
    class Meta:
        model = CostType
        fields = ['name', 'description', 'active']


class ProductCostForm(StyledModelForm):
    class Meta:
        model = ProductCost
        fields = ['product', 'cost_type', 'description', 'amount']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amount'].help_text = 'Custo por unidade da peça. Os componentes são somados no produto.'


class ClientForm(StyledModelForm):
    class Meta:
        model = Client
        fields = ['name', 'document', 'phone', 'email', 'address', 'notes', 'active']


class ContactForm(StyledModelForm):
    class Meta:
        model = Contact
        fields = ['client', 'name', 'relationship', 'phone', 'email', 'notes']

    def clean_client(self):
        client = self.cleaned_data['client']
        if self.instance.pk and self.instance.client_id != client.pk:
            if Consignment.objects.filter(contacts=self.instance).exists():
                raise ValidationError('Este contato já é referência de uma consignação. Cadastre outro contato para a nova cliente.')
        return client


class ConsignmentForm(StyledModelForm):
    class Meta:
        model = Consignment
        fields = ['client', 'sent_date', 'due_date', 'contacts', 'notes']
        widgets = {'contacts': forms.CheckboxSelectMultiple()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client'].queryset = Client.objects.filter(active=True)
        self.fields['contacts'].queryset = Contact.objects.select_related('client').order_by('name')
        self.fields['contacts'].required = False
        self.fields['contacts'].help_text = 'Selecione contatos cadastrados para a cliente escolhida.'
        self.fields['sent_date'].initial = timezone.localdate

    def clean(self):
        data = super().clean()
        client = data.get('client')
        contacts = data.get('contacts')
        if client and contacts and any(contact.client_id != client.pk for contact in contacts):
            self.add_error('contacts', 'Selecione apenas contatos pertencentes à cliente escolhida.')
        start, end = data.get('sent_date'), data.get('due_date')
        if start and end and end < start:
            self.add_error('due_date', 'O prazo de acerto deve ser igual ou posterior ao envio.')
        return data


class ConsignmentItemForm(StyledModelForm):
    class Meta:
        model = ConsignmentItem
        fields = ['product', 'quantity', 'unit_price']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(active=True).select_related('category')
        self.fields['quantity'].min_value = 1
        self.fields['quantity'].initial = 1
        self.fields['unit_price'].required = False

    def clean(self):
        data = super().clean()
        if data.get('product') and data.get('unit_price') is None:
            data['unit_price'] = data['product'].sale_price
        return data


class ItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        products = set()
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue
            product = form.cleaned_data.get('product')
            if product and product.pk in products:
                raise ValidationError('Há produtos repetidos. Some as quantidades em uma única linha.')
            if product:
                products.add(product.pk)


ConsignmentItemFormSet = inlineformset_factory(
    Consignment, ConsignmentItem, form=ConsignmentItemForm, formset=ItemFormSet,
    extra=0, min_num=1, validate_min=True, max_num=100, validate_max=True, can_delete=True,
)


class PaymentForm(StyledModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'paid_date', 'method', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paid_date'].initial = timezone.localdate
        self.fields['amount'].min_value = Decimal('0.01')


class StockForm(forms.Form):
    quantity = forms.IntegerField(label='Quantidade de ajuste', help_text='Ex.: 5 para entrada ou -2 para saída.')
    note = forms.CharField(label='Motivo', max_length=250)

    def clean_quantity(self):
        quantity = self.cleaned_data['quantity']
        if quantity == 0:
            raise ValidationError('Informe uma quantidade diferente de zero.')
        return quantity


class SettlementForm(forms.Form):
    sold = forms.IntegerField(label='Vendidas agora', min_value=0, initial=0)
    returned = forms.IntegerField(label='Devolvidas agora', min_value=0, initial=0)

    def clean(self):
        data = super().clean()
        if data.get('sold') == 0 and data.get('returned') == 0:
            raise ValidationError('Informe ao menos uma peça vendida ou devolvida.')
        return data
