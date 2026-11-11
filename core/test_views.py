from datetime import timedelta
from decimal import Decimal

from django.test import Client as Browser, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Category, Product, Client, Contact, Consignment, ConsignmentItem, Payment
from .services import adjust_stock


class AppWorkflowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Brincos')
        self.product = Product.objects.create(sku='BR-01', name='Argola prata', category=self.category, sale_price=Decimal('125.50'))
        adjust_stock(self.product, 10, 'Estoque de teste')
        self.customer = Client.objects.create(name='Cliente de teste')
        self.contact = Contact.objects.create(client=self.customer, name='Referência de teste')
        self.today = timezone.localdate()

    def draft_data(self, **changes):
        data = {
            'client': self.customer.pk, 'sent_date': self.today.isoformat(),
            'due_date': (self.today + timedelta(days=30)).isoformat(),
            'contacts': [self.contact.pk], 'notes': 'Teste de fluxo',
            'items-TOTAL_FORMS': '1', 'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1', 'items-MAX_NUM_FORMS': '100',
            'items-0-product': self.product.pk, 'items-0-quantity': '4',
            'items-0-unit_price': '125,50',
        }
        data.update(changes)
        return data

    def test_pages_render(self):
        urls = [reverse('dashboard'), reverse('consignment_list'), reverse('consignment_create'), reverse('backups')]
        for entity in ['products', 'categories', 'cost-types', 'costs', 'clients', 'contacts']:
            urls += [reverse('entity_list', args=[entity]), reverse('entity_create', args=[entity])]
        urls += [reverse('entity_edit', args=['products', self.product.pk]), reverse('client_detail', args=[self.customer.pk])]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_full_consignment_workflow_and_localized_money(self):
        response = self.client.post(reverse('consignment_create'), self.draft_data())
        self.assertEqual(response.status_code, 302, response.content.decode()[:1000])
        consignment = Consignment.objects.get()
        item = consignment.items.get()
        self.assertContains(self.client.get(reverse('consignment_detail', args=[consignment.pk])), 'AGUARDANDO ENVIO')
        self.assertEqual(item.unit_price, Decimal('125.50'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(self.client.get(reverse('consignment_detail', args=[consignment.pk])).status_code, 200)
        self.client.post(reverse('consignment_action', args=[consignment.pk]), {'action': 'send'})
        self.assertContains(self.client.get(reverse('consignment_detail', args=[consignment.pk])), 'EM TRÂNSITO')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 6)
        self.client.post(reverse('item_settle', args=[item.pk]), {'sold': '3', 'returned': '1'})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 7)
        self.client.post(reverse('payment_create', args=[consignment.pk]), {
            'amount': '376,50', 'paid_date': self.today.isoformat(), 'method': 'pix', 'notes': '',
        })
        self.assertEqual(Payment.objects.get().amount, Decimal('376.50'))
        self.client.post(reverse('consignment_action', args=[consignment.pk]), {'action': 'close'})
        consignment.refresh_from_db()
        self.assertEqual(consignment.status, 'closed')
        self.assertContains(self.client.get(reverse('consignment_detail', args=[consignment.pk])), 'FINALIZADO')
        self.assertEqual(self.client.get(reverse('consignment_print', args=[consignment.pk])).status_code, 200)

    def test_foreign_reference_rejected(self):
        stranger = Client.objects.create(name='Outra cliente')
        foreign_contact = Contact.objects.create(client=stranger, name='Outro contato')
        response = self.client.post(reverse('consignment_create'), self.draft_data(contacts=[foreign_contact.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Consignment.objects.exists())
        self.assertContains(response, 'Selecione apenas referências')

    def test_duplicate_products_and_invalid_dates_rejected(self):
        data = self.draft_data(**{'items-TOTAL_FORMS': '2', 'items-1-product': self.product.pk,
                                 'items-1-quantity': '1', 'items-1-unit_price': '125,50'})
        self.assertEqual(self.client.post(reverse('consignment_create'), data).status_code, 200)
        self.assertFalse(Consignment.objects.exists())
        data = self.draft_data(due_date=(self.today - timedelta(days=1)).isoformat())
        self.assertEqual(self.client.post(reverse('consignment_create'), data).status_code, 200)
        self.assertFalse(Consignment.objects.exists())

    def test_edit_draft_changes_client_and_references(self):
        self.client.post(reverse('consignment_create'), self.draft_data())
        consignment = Consignment.objects.get()
        item = consignment.items.get()
        other = Client.objects.create(name='Cliente nova')
        new_contact = Contact.objects.create(client=other, name='Referência nova')
        data = self.draft_data(client=other.pk, contacts=[new_contact.pk], **{
            'items-INITIAL_FORMS': '1', 'items-0-id': item.pk,
        })
        response = self.client.post(reverse('consignment_edit', args=[consignment.pk]), data)
        self.assertEqual(response.status_code, 302)
        consignment.refresh_from_db()
        self.assertEqual(consignment.client_id, other.pk)
        self.assertEqual(list(consignment.contacts.values_list('pk', flat=True)), [new_contact.pk])

    def test_crud_and_stock_adjustment(self):
        response = self.client.post(reverse('entity_create', args=['products']), {
            'sku': 'AN-01', 'name': 'Anel lua', 'category': self.category.pk,
            'sale_price': '88,90', 'minimum_stock': 2, 'active': 'on', 'initial_stock': 8,
        })
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(sku='AN-01')
        self.assertEqual(product.stock_quantity, 8)
        self.assertEqual(product.sale_price, Decimal('88.90'))
        self.client.post(reverse('product_stock', args=[product.pk]), {'quantity': -3, 'note': 'Ajuste teste'})
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 5)
        self.client.post(reverse('product_stock', args=[product.pk]), {'quantity': -10, 'note': 'Ajuste inválido'})
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 5)

    def test_get_cannot_change_stock_or_send(self):
        self.client.post(reverse('consignment_create'), self.draft_data())
        consignment = Consignment.objects.get()
        response = self.client.get(reverse('consignment_action', args=[consignment.pk]), {'action': 'send'})
        self.assertEqual(response.status_code, 405)
        consignment.refresh_from_db()
        self.assertEqual(consignment.status, 'draft')
        csrf_browser = Browser(enforce_csrf_checks=True)
        response = csrf_browser.post(reverse('product_stock', args=[self.product.pk]), {'quantity': 10, 'note': 'x'})
        self.assertEqual(response.status_code, 403)
