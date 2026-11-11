import json

from django.core.exceptions import ValidationError
from django.test import TestCase, Client as Browser
from django.urls import reverse
from django.utils import timezone

from .models import Category, Client, Product, Consignment, ConsignmentItem, StockMovement
from .services import send_consignment, settle_item, return_scanned_items


class ScannedReturnTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Joias')
        reseller = Client.objects.create(name='Revendedora')
        self.consignment = Consignment.objects.create(client=reseller, due_date=timezone.localdate())
        self.items = []
        for index in range(2):
            product = Product.objects.create(sku=f'000{index}', name=f'Peça {index}', category=category,
                                              sale_price=10, stock_quantity=10)
            self.items.append(ConsignmentItem.objects.create(consignment=self.consignment, product=product,
                                                            quantity=3, unit_price=10))
        send_consignment(self.consignment)
        self.url = reverse('consignment_returns', args=[self.consignment.pk])

    def entry(self, item, quantity=1):
        item.refresh_from_db()
        return {'item_id': item.pk, 'quantity': quantity,
                'expected_sold': item.sold_quantity, 'expected_returned': item.returned_quantity}

    def test_batch_restores_stock_once_and_keeps_sales(self):
        settle_item(self.items[0], sold=1)
        entries = [self.entry(self.items[0], 2), self.entry(self.items[1], 3)]
        response = self.client.post(self.url, {'entries': json.dumps(entries)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['returned'], 5)
        self.assertEqual(list(Product.objects.order_by('sku').values_list('stock_quantity', flat=True)), [9, 10])
        self.assertEqual(StockMovement.objects.filter(kind='return').count(), 2)
        self.items[0].refresh_from_db()
        self.assertEqual(self.items[0].sold_quantity, 1)
        # A retry after a lost response must not restore stock twice.
        self.assertEqual(self.client.post(self.url, {'entries': json.dumps(entries)}).status_code, 409)
        self.assertEqual(StockMovement.objects.filter(kind='return').count(), 2)

    def test_invalid_member_rolls_back_whole_batch(self):
        entries = [self.entry(self.items[0], 2), self.entry(self.items[1], 4)]
        with self.assertRaises(ValidationError):
            return_scanned_items(self.consignment, entries)
        self.assertFalse(StockMovement.objects.filter(kind='return').exists())
        self.assertEqual(list(Product.objects.order_by('sku').values_list('stock_quantity', flat=True)), [7, 7])

    def test_stale_sale_or_return_rejects_batch(self):
        entries = [self.entry(self.items[0]), self.entry(self.items[1])]
        settle_item(self.items[1], sold=1)
        with self.assertRaisesMessage(ValidationError, 'O acerto mudou'):
            return_scanned_items(self.consignment, entries)
        self.assertFalse(StockMovement.objects.filter(kind='return').exists())

    def test_foreign_item_and_duplicate_are_rejected(self):
        other = Consignment.objects.create(client=self.consignment.client, due_date=timezone.localdate())
        foreign = ConsignmentItem.objects.create(consignment=other, product=self.items[0].product, quantity=1, unit_price=10)
        for entries in [[self.entry(foreign)], [self.entry(self.items[0]), self.entry(self.items[0])]]:
            with self.subTest(entries=entries), self.assertRaises(ValidationError):
                return_scanned_items(self.consignment, entries)
        self.assertFalse(StockMovement.objects.filter(kind='return').exists())

    def test_inactive_product_historical_sku_and_ean_remain_available(self):
        product = self.items[0].product
        product.sku, product.active = 'NEW-SKU', False
        product.save(update_fields=['sku', 'active'])
        response = self.client.get(reverse('consignment_detail', args=[self.consignment.pk]))
        entry = next(row for row in response.context['return_item_data'] if row['id'] == self.items[0].pk)
        self.assertEqual(set(entry['codes']), {'0000', 'NEW-SKU', product.ean13})
        return_scanned_items(self.consignment, [self.entry(self.items[0])])
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 8)

    def test_request_validation_and_status(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(Browser(enforce_csrf_checks=True).post(self.url, {'entries': '[]'}).status_code, 403)
        self.assertEqual(self.client.post(self.url, {'entries': 'not-json'}).status_code, 400)
        for entries in [[], {}, [None], [self.entry(self.items[0], 0)], [self.entry(self.items[0], -1)],
                        [self.entry(self.items[0], 1.5)], [self.entry(self.items[0], True)], [self.entry(self.items[0])] * 101]:
            with self.subTest(entries=entries):
                self.assertEqual(self.client.post(self.url, {'entries': json.dumps(entries)}).status_code, 409)
        for status in ('draft', 'closed', 'cancelled'):
            Consignment.objects.filter(pk=self.consignment.pk).update(status=status)
            with self.subTest(status=status):
                self.assertEqual(self.client.post(self.url, {'entries': json.dumps([self.entry(self.items[0])])}).status_code, 409)
        self.assertFalse(StockMovement.objects.filter(kind='return').exists())
