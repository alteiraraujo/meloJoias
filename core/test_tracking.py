from django.test import TestCase, Client as Browser
from django.urls import reverse
from django.utils import timezone

from .models import Client, Category, Product, Consignment, ConsignmentItem, StockMovement
from .services import send_consignment


class TrackingTests(TestCase):
    def setUp(self):
        client = Client.objects.create(name='Cliente com envio')
        category = Category.objects.create(name='Joias')
        self.product = Product.objects.create(sku='TRACK', name='Anel', category=category, sale_price=10, stock_quantity=5)
        self.consignment = Consignment.objects.create(client=client, due_date=timezone.localdate())
        ConsignmentItem.objects.create(consignment=self.consignment, product=self.product, quantity=2, unit_price=10)
        self.url = reverse('consignment_tracking', args=[self.consignment.pk])

    def test_tracking_after_shipping_does_not_change_stock_or_items(self):
        send_consignment(self.consignment)
        response = self.client.post(self.url, {'tracking_code': ' AA123456789BR ',
                                              'shipping_responsible': ' Ana Melo ', 'shipping_method': ' SEDEX '})
        self.assertEqual(response.status_code, 302)
        self.consignment.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.consignment.tracking_code, 'AA123456789BR')
        self.assertEqual(self.consignment.shipping_responsible, 'Ana Melo')
        self.assertEqual(self.consignment.shipping_method, 'SEDEX')
        self.assertEqual(self.consignment.status, 'sent')
        self.assertEqual(self.product.stock_quantity, 3)
        self.assertEqual(self.consignment.items.get().quantity, 2)
        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertContains(self.client.get(reverse('consignment_print', args=[self.consignment.pk])), 'AA123456789BR')
        self.assertContains(self.client.get(reverse('consignment_print', args=[self.consignment.pk])), 'Ana Melo')
        self.assertContains(self.client.get(reverse('consignment_print', args=[self.consignment.pk])), 'SEDEX')

    def test_shipping_fields_validation_and_finalized_consignment(self):
        url = reverse('consignment_print', args=[self.consignment.pk])
        self.assertContains(self.client.get(url), 'class="tracking-blank"', count=3)
        for field, size in [('shipping_responsible', 161), ('shipping_method', 81)]:
            self.client.post(self.url, {'tracking_code': 'DO-NOT-SAVE', field: 'X' * size})
            self.consignment.refresh_from_db()
            self.assertEqual(self.consignment.tracking_code, '')
            self.assertEqual(getattr(self.consignment, field), '')
        Consignment.objects.filter(pk=self.consignment.pk).update(status='closed')
        self.client.post(self.url, {'shipping_responsible': '<script>test</script>',
                                    'shipping_method': 'Transportadora própria', 'tracking_code': 'COD123'})
        self.consignment.refresh_from_db()
        self.assertEqual(self.consignment.status, 'closed')
        response = self.client.get(url)
        self.assertContains(response, '&lt;script&gt;test&lt;/script&gt;')
        self.assertNotContains(response, '<script>test</script>')
        self.assertContains(response, 'Transportadora própria')
        self.client.post(self.url, {'shipping_responsible': '', 'shipping_method': '', 'tracking_code': ''})
        self.assertContains(self.client.get(url), 'class="tracking-blank"', count=3)

    def test_optional_tracking_and_invalid_value(self):
        self.assertContains(self.client.get(reverse('consignment_print', args=[self.consignment.pk])), 'Código de rastreio')
        self.client.post(self.url, {'tracking_code': 'X' * 81})
        self.consignment.refresh_from_db()
        self.assertEqual(self.consignment.tracking_code, '')
        self.client.post(self.url, {'tracking_code': '<script>test</script>'})
        response = self.client.get(reverse('consignment_print', args=[self.consignment.pk]))
        self.assertContains(response, '&lt;script&gt;test&lt;/script&gt;')
        self.client.post(self.url, {'tracking_code': ''})
        self.consignment.refresh_from_db()
        self.assertEqual(self.consignment.tracking_code, '')

    def test_tracking_requires_post_csrf_and_non_cancelled_consignment(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(Browser(enforce_csrf_checks=True).post(self.url, {'tracking_code': 'AA123456789BR'}).status_code, 403)
        self.consignment.status = 'cancelled'
        self.consignment.save()
        self.client.post(self.url, {'tracking_code': 'AA123456789BR', 'shipping_responsible': 'Ana', 'shipping_method': 'PAC'})
        self.consignment.refresh_from_db()
        self.assertEqual(self.consignment.tracking_code, '')
        self.assertEqual(self.consignment.shipping_responsible, '')
        self.assertEqual(self.consignment.shipping_method, '')
