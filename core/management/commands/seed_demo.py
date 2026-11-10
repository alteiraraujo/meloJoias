from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import (
    Category, Client, Consignment, ConsignmentContact, ConsignmentItem, Contact,
    CostType, Product, ProductCost, StockMovement,
)
from core.services import add_payment, close_consignment, send_consignment, settle_item


class Command(BaseCommand):
    help = 'Preenche um banco vazio com dados fictícios para demonstração. Nunca é executado automaticamente.'

    @transaction.atomic
    def handle(self, *args, **options):
        if any(model.objects.exists() for model in [Category, Product, CostType, Client, Consignment]):
            raise CommandError('O banco já contém cadastros. A demonstração só pode ser criada em um banco vazio.')

        today = timezone.localdate()
        demo_note = 'DADOS FICTÍCIOS — cadastro de demonstração; não representa uma pessoa ou operação real.'
        categories = {name: Category.objects.create(name=name) for name in ['Anéis', 'Brincos', 'Colares', 'Pulseiras']}
        acquisition = CostType.objects.create(name='Aquisição', description='Valor de compra de cada peça.')
        packaging = CostType.objects.create(name='Embalagem', description='Caixinha e apresentação por peça.')
        products = []
        specifications = [
            ('MJ-BR-001', 'Brinco Argola Essencial', 'Brincos', '89.90', '32.00', 24, 5, 'Argola delicada com acabamento dourado.'),
            ('MJ-CL-001', 'Colar Ponto de Luz', 'Colares', '129.90', '49.00', 18, 4, 'Corrente fina com ponto de luz central.'),
            ('MJ-AN-001', 'Anel Solitário Aurora', 'Anéis', '119.90', '43.00', 12, 3, 'Aro delicado com pedra central transparente.'),
            ('MJ-PL-001', 'Pulseira Elo Dourado', 'Pulseiras', '99.90', '36.00', 16, 4, 'Elos clássicos com acabamento dourado.'),
            ('MJ-BR-002', 'Brinco Gota Cristal', 'Brincos', '149.90', '58.00', 9, 3, 'Cristal em formato de gota para ocasiões especiais.'),
            ('MJ-CL-002', 'Colar Pérola Serena', 'Colares', '159.90', '62.00', 8, 3, 'Pérola sintética em corrente de desenho minimalista.'),
            ('MJ-AN-002', 'Anel Duplo Delicado', 'Anéis', '79.90', '27.00', 14, 3, 'Duas linhas finas com acabamento polido.'),
            ('MJ-PL-002', 'Pulseira Riviera Luz', 'Pulseiras', '189.90', '75.00', 6, 3, 'Sequência de cristais em uma pulseira elegante.'),
            ('MJ-BR-003', 'Brinco Pérola Clássica', 'Brincos', '69.90', '23.00', 20, 5, 'Pequeno ponto de pérola sintética.'),
            ('MJ-CL-003', 'Colar Medalha Afeto', 'Colares', '109.90', '39.00', 10, 3, 'Medalha redonda com corrente ajustável.'),
        ]
        for sku, name, category, price, cost, stock, minimum, description in specifications:
            product = Product.objects.create(sku=sku, name=name, category=categories[category],
                                             sale_price=Decimal(price), stock_quantity=stock,
                                             minimum_stock=minimum, description=description)
            ProductCost.objects.create(product=product, cost_type=acquisition, amount=Decimal(cost))
            ProductCost.objects.create(product=product, cost_type=packaging, amount=Decimal('4.50'))
            StockMovement.objects.create(product=product, kind=StockMovement.Kind.IN, quantity=stock,
                                         note='Estoque inicial fictício de demonstração')
            products.append(product)

        clients = []
        for name, contact_name, relationship in [
            ('Ana Beatriz Lima', 'Marina Lima', 'Referência familiar'),
            ('Camila Rodrigues', 'Clara Rodrigues', 'Referência familiar'),
            ('Fernanda Alves', 'Helena Alves', 'Referência comercial'),
            ('Juliana Martins', 'Laura Martins', 'Referência familiar'),
            ('Renata Costa', 'Sofia Costa', 'Referência comercial'),
        ]:
            client = Client.objects.create(name=name, notes=demo_note)
            Contact.objects.create(client=client, name=contact_name, relationship=relationship, notes=demo_note)
            clients.append(client)

        def consignment(client, sent_days, due_days, lines, note, send=True):
            record = Consignment.objects.create(client=client, sent_date=today + timedelta(days=sent_days),
                                                due_date=today + timedelta(days=due_days),
                                                notes=f'{note}\n{demo_note}')
            ConsignmentContact.objects.create(consignment=record, contact=client.contacts.first())
            for product_index, quantity in lines:
                product = products[product_index]
                ConsignmentItem.objects.create(consignment=record, product=product,
                                               quantity=quantity, unit_price=product.sale_price)
            if send:
                send_consignment(record)
            return record

        first = consignment(clients[0], -10, 5, [(0, 6), (1, 4), (3, 3)], 'Seleção de essenciais para apresentação.')
        first_item = first.items.get(product=products[0])
        settle_item(first_item, sold=3)
        settle_item(first.items.get(product=products[1]), sold=2)
        add_payment(first, Decimal('300.00'), today - timedelta(days=2), 'pix', 'Recebimento parcial fictício')

        overdue = consignment(clients[1], -21, -3, [(4, 6), (5, 5), (7, 4)], 'Acerto com prazo vencido para demonstrar o alerta.')
        settle_item(overdue.items.get(product=products[4]), sold=2, returned=1)

        consignment(clients[2], -3, 12, [(2, 4), (6, 5), (8, 6)], 'Seleção da coleção delicada.')

        complete = consignment(clients[3], -30, -15, [(0, 3), (9, 2)], 'Exemplo de consignação encerrada.')
        settle_item(complete.items.get(product=products[0]), sold=2, returned=1)
        settle_item(complete.items.get(product=products[9]), sold=1, returned=1)
        add_payment(complete, complete.sold_value, today - timedelta(days=16), 'pix', 'Acerto final fictício')
        close_consignment(complete)

        consignment(clients[4], 0, 15, [(1, 3), (3, 4), (8, 4)], 'Seleção preparada, aguardando envio.', send=False)
        self.stdout.write(self.style.SUCCESS('Demonstração criada: 10 produtos, 5 clientes e 5 consignações. Todos os dados são fictícios.'))
