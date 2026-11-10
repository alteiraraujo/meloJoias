from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import forms, services
from .models import (Category, Product, CostType, ProductCost, Client, Contact,
                     Consignment, ConsignmentItem, Payment, StockMovement)
from .templatetags.money import brl


ENTITIES = {
    'products': (Product, forms.ProductForm, 'Produtos', 'Seu catálogo, preços e disponibilidade.', 'Novo produto'),
    'categories': (Category, forms.CategoryForm, 'Categorias', 'Organize as peças da sua coleção.', 'Nova categoria'),
    'cost-types': (CostType, forms.CostTypeForm, 'Tipos de custo', 'Defina os componentes do custo de cada peça.', 'Novo tipo de custo'),
    'costs': (ProductCost, forms.ProductCostForm, 'Custos', 'Composição do custo por unidade de cada produto.', 'Novo custo'),
    'clients': (Client, forms.ClientForm, 'Clientes', 'Relacionamentos que fazem sua marca crescer.', 'Nova cliente'),
    'contacts': (Contact, forms.ContactForm, 'Contatos', 'Referências e contatos vinculados às suas clientes.', 'Novo contato'),
}


def entity_config(entity):
    if entity not in ENTITIES:
        raise Http404('Cadastro não encontrado.')
    return ENTITIES[entity]


def consignment_queryset():
    return Consignment.objects.select_related('client').prefetch_related('items__product', 'payments', 'contacts')


def show_errors(request, error):
    for message in error.messages:
        messages.error(request, message)


def dashboard(request):
    today = timezone.localdate()
    all_consignments = list(consignment_queryset())
    active = [c for c in all_consignments if c.status == 'sent']
    products = list(Product.objects.filter(active=True).select_related('category').prefetch_related('costs'))
    metrics = {
        'consigned_value': sum((i.pending_quantity * i.unit_price for c in active for i in c.items.all()), Decimal(0)),
        'available_value': sum((p.stock_value for p in products), Decimal(0)),
        'receivable_value': sum((c.balance for c in active), Decimal(0)),
        'active_count': len(active), 'available_count': sum(p.stock_quantity for p in products),
        'pending_count': sum(c.pending_quantity for c in active),
        'client_count': Client.objects.filter(active=True).count(),
        'overdue_count': sum(c.is_overdue for c in active),
    }
    categories = list(Category.objects.filter(active=True))
    total_stock = metrics['available_count'] or 1
    category_stats = []
    for category in categories:
        count = sum(p.stock_quantity for p in products if p.category_id == category.pk)
        category_stats.append({'name': category.name, 'count': count, 'percent': round(100 * count / total_stock)})
    return render(request, 'dashboard.html', {
        'nav_active': 'dashboard', 'metrics': metrics, 'consignments': all_consignments[:5],
        'low_stock': [p for p in products if p.stock_quantity <= p.minimum_stock][:5],
        'recent_movements': StockMovement.objects.select_related('product', 'consignment')[:6],
        'categories': categories, 'category_stats': category_stats,
        'due_consignments': sorted(active, key=lambda c: c.due_date)[:4], 'date_today': today,
    })


def entity_list(request, entity):
    model, form_class, title, subtitle, create_label = entity_config(entity)
    queryset = model.objects.all()
    q = request.GET.get('q', '').strip()
    if entity == 'products':
        queryset = queryset.select_related('category').prefetch_related('costs')
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(ean13__icontains=q) | Q(category__name__icontains=q))
        if request.GET.get('category', '').isdigit():
            queryset = queryset.filter(category_id=request.GET['category'])
        columns = ['Produto', 'Categoria', 'Preço de venda', 'Custo / un.', 'Estoque', 'Situação']
    elif entity == 'clients':
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(document__icontains=q) | Q(phone__icontains=q))
        columns = ['Cliente', 'Telefone', 'E-mail', 'Documento', 'Situação']
    elif entity == 'contacts':
        queryset = queryset.select_related('client')
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(client__name__icontains=q) | Q(phone__icontains=q))
        columns = ['Contato', 'Cliente', 'Vínculo', 'Telefone', 'E-mail']
    elif entity == 'costs':
        queryset = queryset.select_related('product', 'cost_type')
        if q:
            queryset = queryset.filter(Q(product__name__icontains=q) | Q(cost_type__name__icontains=q) | Q(description__icontains=q))
        columns = ['Produto', 'Tipo de custo', 'Descrição', 'Custo / un.']
    else:
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(description__icontains=q))
        columns = ['Nome', 'Descrição', 'Situação']
    page = Paginator(queryset, 20).get_page(request.GET.get('page'))
    rows = []
    for obj in page:
        active = 'Ativo' if getattr(obj, 'active', True) else 'Inativo'
        if entity == 'products':
            cells = [f'{obj.sku} · {obj.name}', obj.category.name, brl(obj.sale_price), brl(obj.total_cost), str(obj.stock_quantity), active]
        elif entity == 'clients':
            cells = [obj.name, obj.phone or '—', obj.email or '—', obj.document or '—', active]
        elif entity == 'contacts':
            cells = [obj.name, obj.client.name, obj.relationship or '—', obj.phone or '—', obj.email or '—']
        elif entity == 'costs':
            cells = [obj.product.name, obj.cost_type.name, obj.description or '—', brl(obj.amount)]
        else:
            cells = [obj.name, obj.description or '—', active]
        rows.append({'object': obj, 'cells': cells,
                     'edit_url': reverse('entity_edit', args=[entity, obj.pk]),
                     'delete_url': reverse('entity_delete', args=[entity, obj.pk]),
                     'detail_url': reverse('client_detail', args=[obj.pk]) if entity == 'clients' else None})
    return render(request, 'entity_list.html', {
        'nav_active': entity, 'entity': entity, 'title': title, 'subtitle': subtitle,
        'create_label': create_label, 'columns': columns, 'rows': rows, 'q': q,
        'products': page.object_list if entity == 'products' else [], 'page_obj': page,
        'categories': Category.objects.all(), 'count': page.paginator.count,
    })


def entity_form(request, entity, pk=None):
    model, form_class, title, subtitle, create_label = entity_config(entity)
    obj = get_object_or_404(model, pk=pk) if pk else None
    initial = {}
    for field in ('client', 'product'):
        value = request.GET.get(field, '')
        if value.isdigit():
            initial[field] = int(value)
    form = form_class(request.POST or None, instance=obj, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                if entity == 'products' and pk:
                    saved = form.save(commit=False)
                    saved.save(update_fields=list(forms.ProductForm.Meta.fields) + ['updated_at'])
                else:
                    saved = form.save()
                if entity == 'products' and not pk and form.cleaned_data.get('initial_stock'):
                    services.adjust_stock(saved, form.cleaned_data['initial_stock'], 'Estoque inicial do cadastro')
            messages.success(request, 'Cadastro salvo com sucesso.')
            return redirect('entity_list', entity=entity)
        except ValidationError as error:
            form.add_error(None, error)
        except IntegrityError:
            form.add_error(None, 'Já existe um cadastro com estes dados. Confira o código ou o nome informado.')
    return render(request, 'entity_form.html', {
        'nav_active': entity, 'entity': entity, 'form': form, 'object': obj,
        'title': f'Editar {model._meta.verbose_name}' if pk else create_label,
        'subtitle': subtitle, 'back_url': reverse('entity_list', args=[entity]),
        'product_costs': obj.costs.select_related('cost_type') if entity == 'products' and obj else [],
        'stock_form': forms.StockForm() if entity == 'products' and obj else None,
    })


def entity_delete(request, entity, pk):
    model, _, _, _, _ = entity_config(entity)
    obj = get_object_or_404(model, pk=pk)
    if request.method == 'POST':
        try:
            obj.delete()
            messages.success(request, 'Cadastro excluído.')
            return redirect('entity_list', entity=entity)
        except ProtectedError:
            messages.error(request, 'Este cadastro tem histórico vinculado e não pode ser excluído. Quando disponível, desmarque “Ativo” na edição.')
            return redirect('entity_edit', entity=entity, pk=pk)
    return render(request, 'confirm_delete.html', {
        'nav_active': entity, 'object': obj, 'entity': entity, 'title': 'Excluir cadastro',
        'back_url': reverse('entity_list', args=[entity]),
    })


def client_detail(request, pk):
    client = get_object_or_404(Client.objects.prefetch_related('contacts'), pk=pk)
    return render(request, 'client_detail.html', {'nav_active': 'clients', 'title': client.name, 'client': client,
        'consignments': consignment_queryset().filter(client=client)})


def consignment_list(request):
    queryset = consignment_queryset()
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    if q:
        condition = Q(client__name__icontains=q)
        numeric = q.upper().removeprefix('MJ-')
        if numeric.isdigit():
            condition |= Q(pk=int(numeric))
        queryset = queryset.filter(condition)
    if status in dict(Consignment.Status.choices):
        queryset = queryset.filter(status=status)
    elif status == 'overdue':
        queryset = queryset.filter(status='sent', due_date__lt=timezone.localdate())
    page = Paginator(queryset, 20).get_page(request.GET.get('page'))
    return render(request, 'consignment_list.html', {
        'nav_active': 'consignments', 'title': 'Consignações', 'consignments': page, 'page_obj': page,
        'q': q, 'status': status, 'status_choices': Consignment.Status.choices,
        'count': page.paginator.count,
    })


def _consignment_form(request, instance):
    form = forms.ConsignmentForm(request.POST or None, instance=instance)
    formset = forms.ConsignmentItemFormSet(request.POST or None, instance=instance, prefix='items')
    if request.method == 'POST':
        valid_form, valid_items = form.is_valid(), formset.is_valid()
        if valid_form and valid_items:
            try:
                with transaction.atomic():
                    if instance.pk:
                        current = Consignment.objects.select_for_update().get(pk=instance.pk)
                        if current.status != 'draft':
                            raise ValidationError('A consignação já foi enviada e não pode mais ser editada.')
                    saved = form.save(commit=False)
                    if saved.pk:
                        saved.contacts.clear()
                    saved.save()
                    form.save_m2m()
                    formset.instance = saved
                    formset.save()
                messages.success(request, 'Rascunho salvo. Confira as peças e confirme o envio para movimentar o estoque.')
                return redirect('consignment_detail', pk=saved.pk)
            except ValidationError as error:
                form.add_error(None, error)
            except IntegrityError:
                form.add_error(None, 'Não foi possível salvar. Confira se há produtos repetidos ou dados inválidos.')
    return render(request, 'consignment_form.html', {
        'nav_active': 'consignments', 'form': form, 'formset': formset, 'consignment': instance,
        'title': f'Editar {instance.code}' if instance.pk else 'Nova consignação',
        'product_data': [{'id': p.pk, 'sku': p.sku, 'ean13': p.ean13, 'name': p.name, 'price': str(p.sale_price), 'stock': p.stock_quantity}
                         for p in Product.objects.filter(active=True)],
        'contact_data': list(Contact.objects.values('id', 'client_id', 'name', 'phone')),
    })


def consignment_create(request):
    instance = Consignment(sent_date=timezone.localdate(), due_date=timezone.localdate() + timezone.timedelta(days=30))
    if request.GET.get('client', '').isdigit():
        instance.client_id = int(request.GET['client'])
    return _consignment_form(request, instance)


def consignment_edit(request, pk):
    instance = get_object_or_404(Consignment, pk=pk)
    if instance.status != 'draft':
        messages.error(request, 'Somente rascunhos podem ser editados.')
        return redirect('consignment_detail', pk=pk)
    return _consignment_form(request, instance)


def consignment_detail(request, pk):
    consignment = get_object_or_404(consignment_queryset(), pk=pk)
    return render(request, 'consignment_detail.html', {
        'nav_active': 'consignments', 'title': consignment.code, 'consignment': consignment, 'items': consignment.items.all(),
        'contacts': consignment.contacts.all(), 'payments': consignment.payments.all(),
        'payment_form': forms.PaymentForm(initial={'amount': consignment.balance}),
    })


@require_POST
def consignment_action(request, pk):
    consignment = get_object_or_404(Consignment, pk=pk)
    action = request.POST.get('action')
    handlers = {'send': (services.send_consignment, 'Envio confirmado. Estoque atualizado.'),
                'close': (services.close_consignment, 'Consignação encerrada com todas as peças e recebimentos conferidos.'),
                'cancel': (services.cancel_consignment, 'Rascunho cancelado.')}
    if action not in handlers:
        return HttpResponseBadRequest('Ação inválida.')
    try:
        handler, message = handlers[action]
        handler(consignment)
        messages.success(request, message)
    except ValidationError as error:
        show_errors(request, error)
    return redirect('consignment_detail', pk=pk)


@require_POST
def item_settle(request, pk):
    item = get_object_or_404(ConsignmentItem, pk=pk)
    form = forms.SettlementForm(request.POST)
    if form.is_valid():
        try:
            services.settle_item(item, **form.cleaned_data)
            messages.success(request, 'Vendas e devoluções registradas. Estoque atualizado.')
        except ValidationError as error:
            show_errors(request, error)
    else:
        for error_list in form.errors.values():
            for error in error_list:
                messages.error(request, error)
    return redirect('consignment_detail', pk=item.consignment_id)


@require_POST
def payment_create(request, pk):
    consignment = get_object_or_404(Consignment, pk=pk)
    form = forms.PaymentForm(request.POST, instance=Payment(consignment=consignment))
    if form.is_valid():
        try:
            services.add_payment(consignment, **form.cleaned_data)
            messages.success(request, 'Recebimento registrado com sucesso.')
        except ValidationError as error:
            show_errors(request, error)
    else:
        for error_list in form.errors.values():
            for error in error_list:
                messages.error(request, error)
    return redirect('consignment_detail', pk=pk)


@require_POST
def product_stock(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = forms.StockForm(request.POST)
    if form.is_valid():
        try:
            services.adjust_stock(product, **form.cleaned_data)
            messages.success(request, 'Estoque ajustado e movimentação registrada.')
        except ValidationError as error:
            show_errors(request, error)
    else:
        for error_list in form.errors.values():
            for error in error_list:
                messages.error(request, error)
    return redirect('entity_edit', entity='products', pk=pk)


def product_label(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'product_label.html', {'product': product})


def product_barcode(request, pk):
    from barcode import EAN13
    product = get_object_or_404(Product, pk=pk)
    svg = EAN13(product.ean13[:12]).render(writer_options={
        'module_width': 0.33, 'module_height': 22.85, 'quiet_zone': 3.63,
        'font_size': 10, 'text_distance': 3, 'background': 'white', 'foreground': 'black',
    })
    return HttpResponse(svg, content_type='image/svg+xml')


def consignment_print(request, pk):
    consignment = get_object_or_404(consignment_queryset(), pk=pk)
    return render(request, 'consignment_print.html', {'consignment': consignment, 'items': consignment.items.all(),
                  'contacts': consignment.contacts.all(), 'date_today': timezone.localdate()})


def backups(request):
    folder = settings.BASE_DIR / 'backups'
    files = [{'name': p.name, 'size': p.stat().st_size, 'modified': timezone.datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.get_current_timezone())}
             for p in sorted([*folder.glob('*.dump'), *folder.glob('*.sqlite3')], reverse=True)] if folder.exists() else []
    return render(request, 'backups.html', {'nav_active': 'backups', 'title': 'Backup e dados', 'backups': files})


def backup_download(request):
    from scripts.backup import BackupError, create_backup
    try:
        path = create_backup()
    except BackupError as error:
        messages.error(request, str(error))
        return redirect('backups')
    return FileResponse(path.open('rb'), as_attachment=True, filename=path.name, content_type='application/octet-stream')
