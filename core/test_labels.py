from decimal import Decimal
from unittest.mock import patch
from xml.etree import ElementTree

from barcode import EAN13
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .labels import generate_internal_ean, validate_ean13
from .models import Category, Product
from .services import adjust_stock


class LabelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Joias')
        self.product = Product.objects.create(sku='000123', name='Anel', category=self.category,
                                              sale_price=Decimal('39.90'))

    def test_ean_is_valid_unique_and_stable_across_edits(self):
        code = self.product.ean13
        self.assertEqual(len(code), 13)
        self.assertTrue(code.startswith('20'))
        validate_ean13(code)
        other = Product.objects.create(sku='OTHER', name='Outro', category=self.category, sale_price=1)
        self.assertNotEqual(code, other.ean13)
        self.product.name = 'Nome atualizado'
        self.product.save()
        adjust_stock(self.product, 5, 'Teste')
        self.product.refresh_from_db()
        self.assertEqual(self.product.ean13, code)

    def test_invalid_checksums_and_non_ascii_rejected(self):
        validate_ean13('4006381333931')
        for value in ['4006381333932', '123', '４００６３８１３３３９３１']:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_ean13(value)

    def test_generator_avoids_existing_sku_and_ean(self):
        self.product.ean13 = EAN13('200000000001').get_fullcode()
        self.product.sku = EAN13('200000000002').get_fullcode()
        self.product.save()
        with patch('core.labels.randbelow', side_effect=[1, 2, 3]):
            self.assertEqual(generate_internal_ean(), EAN13('200000000003').get_fullcode())

    def test_label_and_svg_match_product_and_search_accepts_ean(self):
        response = self.client.get(reverse('product_label', args=[self.product.pk]))
        self.assertContains(response, self.product.ean13)
        response = self.client.get(reverse('product_barcode', args=[self.product.pk]))
        self.assertEqual(response['Content-Type'], 'image/svg+xml')
        svg = ElementTree.fromstring(response.content)
        self.assertIn(self.product.ean13, ''.join(svg.itertext()))
        self.assertTrue(svg.findall('.//{http://www.w3.org/2000/svg}rect'))
        response = self.client.get(reverse('entity_list', args=['products']), {'q': self.product.ean13})
        self.assertContains(response, self.product.name)

    def test_scanner_receives_codes_and_only_active_products(self):
        response = self.client.get(reverse('consignment_create'))
        self.assertEqual(response.context['product_data'][0]['sku'], '000123')
        self.assertEqual(response.context['product_data'][0]['ean13'], self.product.ean13)
        self.product.active = False
        self.product.save()
        response = self.client.get(reverse('consignment_create'))
        self.assertEqual(response.context['product_data'], [])


class LabelMigrationTests(TransactionTestCase):
    def test_existing_products_keep_data_and_receive_unique_codes(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('core', '0001_initial')])
        try:
            apps = executor.loader.project_state([('core', '0001_initial')]).apps
            CategoryBefore = apps.get_model('core', 'Category')
            ProductBefore = apps.get_model('core', 'Product')
            category = CategoryBefore.objects.create(name='Antes da atualização')
            first = ProductBefore.objects.create(sku=EAN13('200000000001').get_fullcode(),
                name='Produto existente', category=category, sale_price=Decimal('57.90'), stock_quantity=7)
            second = ProductBefore.objects.create(sku='OLD-02', name='Outro existente',
                category=category, sale_price=1, stock_quantity=0)
        finally:
            MigrationExecutor(connection).migrate([('core', '0002_product_ean13')])
        product = Product.objects.get(pk=first.pk)
        self.assertEqual(product.sku, first.sku)
        self.assertEqual(product.sale_price, Decimal('57.90'))
        self.assertEqual(product.stock_quantity, 7)
        self.assertNotEqual(product.ean13, first.sku)
        self.assertNotEqual(product.ean13, Product.objects.get(pk=second.pk).ean13)
        validate_ean13(product.ean13)
