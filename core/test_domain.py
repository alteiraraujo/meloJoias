from datetime import timedelta
from decimal import Decimal
from io import StringIO
import subprocess
import sys
import textwrap

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .models import (
    Category, Client, Consignment, ConsignmentContact, ConsignmentItem, Contact,
    CostType, Payment, Product, ProductCost, StockMovement,
)
from .services import add_payment, adjust_stock, cancel_consignment, close_consignment, send_consignment, settle_item


class DomainTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.category = Category.objects.create(name='Brincos')
        self.client = Client.objects.create(name='Cliente fictícia')
        self.product = Product.objects.create(sku='P-01', name='Brinco', category=self.category,
                                              sale_price=Decimal('19.90'), stock_quantity=10)
        self.consignment = Consignment.objects.create(client=self.client, sent_date=self.today,
                                                      due_date=self.today + timedelta(days=15))
        self.item = ConsignmentItem.objects.create(consignment=self.consignment, product=self.product,
                                                   quantity=4, unit_price=Decimal('19.90'))

    def test_send_reserves_stock_once_and_snapshots_historical_data(self):
        cost_type = CostType.objects.create(name='Compra')
        ProductCost.objects.create(product=self.product, cost_type=cost_type, amount=Decimal('7.15'))
        send_consignment(self.consignment)
        self.product.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 6)
        self.assertEqual(self.item.product_name, 'Brinco')
        self.assertEqual(self.item.product_sku, 'P-01')
        self.assertEqual(self.item.unit_cost, Decimal('7.15'))
        self.assertEqual(self.consignment.status, 'sent')
        self.assertEqual(self.consignment.total_value, Decimal('79.60'))
        movement = StockMovement.objects.get()
        self.assertEqual((movement.kind, movement.quantity), ('out', -4))
        with self.assertRaises(ValidationError):
            send_consignment(self.consignment)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 6)

    def test_insufficient_stock_rolls_back_entire_shipment(self):
        other = Product.objects.create(sku='P-02', name='Colar', category=self.category,
                                       sale_price=Decimal('29.90'), stock_quantity=1)
        ConsignmentItem.objects.create(consignment=self.consignment, product=other, quantity=2, unit_price=other.sale_price)
        with self.assertRaises(ValidationError):
            send_consignment(self.consignment)
        self.product.refresh_from_db()
        self.consignment.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(self.consignment.status, 'draft')
        self.assertFalse(StockMovement.objects.exists())

    def test_empty_or_inactive_consignment_cannot_be_sent(self):
        self.item.delete()
        with self.assertRaises(ValidationError):
            send_consignment(self.consignment)
        self.item = ConsignmentItem.objects.create(consignment=self.consignment, product=self.product,
                                                   quantity=1, unit_price=Decimal('19.90'))
        self.client.active = False
        self.client.save()
        with self.assertRaises(ValidationError):
            send_consignment(self.consignment)
        self.client.active = True
        self.client.save()
        self.product.active = False
        self.product.save()
        with self.assertRaises(ValidationError):
            send_consignment(self.consignment)

    def test_returns_restore_stock_and_sales_do_not_double_deduct(self):
        send_consignment(self.consignment)
        settle_item(self.item, sold=1, returned=1)
        settle_item(self.item, sold=1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 7)
        self.assertEqual((self.item.sold_quantity, self.item.returned_quantity, self.item.pending_quantity), (2, 1, 1))
        self.assertEqual(self.consignment.sold_value, Decimal('39.80'))
        self.assertEqual(StockMovement.objects.filter(kind='return').get().quantity, 1)

    def test_stale_item_is_reloaded_before_settlement(self):
        send_consignment(self.consignment)
        stale = ConsignmentItem.objects.get(pk=self.item.pk)
        settle_item(self.item, sold=3)
        with self.assertRaises(ValidationError):
            settle_item(stale, returned=2)
        self.item.refresh_from_db()
        self.assertEqual(self.item.sold_quantity, 3)
        self.assertEqual(self.item.returned_quantity, 0)

    def test_invalid_settlement_does_not_change_stock_or_totals(self):
        with self.assertRaises(ValidationError):
            settle_item(self.item, sold=1)
        send_consignment(self.consignment)
        for sold, returned in [(-1, 0), (0, -1), (3, 2), (0, 0), (1.5, 0), (True, 0)]:
            with self.subTest(sold=sold, returned=returned), self.assertRaises(ValidationError):
                settle_item(self.item, sold=sold, returned=returned)
        self.item.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.item.pending_quantity, 4)
        self.assertEqual(self.product.stock_quantity, 6)

    def test_payments_are_capped_at_recorded_sales_and_use_exact_decimals(self):
        send_consignment(self.consignment)
        with self.assertRaises(ValidationError):
            add_payment(self.consignment, Decimal('0.01'), self.today, 'pix')
        settle_item(self.item, sold=2)
        add_payment(self.consignment, Decimal('10.10'), self.today, 'pix')
        self.assertEqual(self.consignment.balance, Decimal('29.70'))
        with self.assertRaises(ValidationError):
            add_payment(self.consignment, Decimal('29.71'), self.today, 'cash')
        add_payment(self.consignment, '29.70', self.today, 'cash')
        self.assertEqual(self.consignment.balance, Decimal('0.00'))
        self.assertEqual(Payment.objects.count(), 2)

    def test_invalid_payment_amounts_are_rejected(self):
        send_consignment(self.consignment)
        settle_item(self.item, sold=4)
        for amount in ['0', '-1', '1.001', 'NaN', 'Infinity', 0.1, True]:
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                add_payment(self.consignment, amount, self.today, 'pix')
        self.assertFalse(Payment.objects.exists())

    def test_close_requires_all_pieces_accounted_for_and_paid(self):
        with self.assertRaises(ValidationError):
            close_consignment(self.consignment)
        send_consignment(self.consignment)
        with self.assertRaises(ValidationError):
            close_consignment(self.consignment)
        settle_item(self.item, sold=3, returned=1)
        with self.assertRaises(ValidationError):
            close_consignment(self.consignment)
        add_payment(self.consignment, Decimal('59.70'), self.today, 'pix')
        close_consignment(self.consignment)
        self.assertEqual(self.consignment.status, 'closed')
        self.assertEqual(self.consignment.pending_quantity, 0)
        with self.assertRaises(ValidationError):
            settle_item(self.item, sold=1)
        with self.assertRaises(ValidationError):
            add_payment(self.consignment, '1', self.today, 'pix')

    def test_all_returns_can_close_without_payment(self):
        send_consignment(self.consignment)
        settle_item(self.item, returned=4)
        close_consignment(self.consignment)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(self.consignment.balance, Decimal('0.00'))

    def test_only_drafts_can_be_cancelled_without_stock_changes(self):
        cancel_consignment(self.consignment)
        self.assertEqual(self.consignment.status, 'cancelled')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertFalse(StockMovement.objects.exists())
        with self.assertRaises(ValidationError):
            send_consignment(self.consignment)
        sent = Consignment.objects.create(client=self.client, sent_date=self.today, due_date=self.today)
        ConsignmentItem.objects.create(consignment=sent, product=self.product, quantity=1, unit_price=Decimal('19.90'))
        send_consignment(sent)
        with self.assertRaises(ValidationError):
            cancel_consignment(sent)

    def test_stock_adjustments_are_audited_and_cannot_make_stock_negative(self):
        adjust_stock(self.product, 2, 'Entrada recebida')
        adjust_stock(self.product, -3, 'Conferência física')
        self.assertEqual(self.product.stock_quantity, 9)
        self.assertEqual(StockMovement.objects.count(), 2)
        for quantity, note in [(-10, 'Falta'), (0, 'Nada'), (1, ''), (1.5, 'Fracionado')]:
            with self.subTest(quantity=quantity, note=note), self.assertRaises(ValidationError):
                adjust_stock(self.product, quantity, note)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 9)
        self.assertEqual(StockMovement.objects.count(), 2)

    def test_references_must_belong_to_selected_client(self):
        other = Client.objects.create(name='Outra cliente')
        wrong = Contact.objects.create(client=other, name='Outra referência')
        with self.assertRaises(ValidationError):
            ConsignmentContact.objects.create(consignment=self.consignment, contact=wrong)
        contact = Contact.objects.create(client=self.client, name='Referência certa')
        ConsignmentContact.objects.create(consignment=self.consignment, contact=contact)
        contact.client = other
        with self.assertRaises(ValidationError):
            contact.save()
        # A draft can change its client while the form replaces its contacts.
        # Shipping remains the final integrity gate for any stale references.
        self.consignment.client = other
        self.consignment.save()
        with self.assertRaises(ValidationError):
            send_consignment(self.consignment)

    def test_dates_and_duplicate_products_are_validated(self):
        self.consignment.due_date = self.today - timedelta(days=1)
        with self.assertRaises(ValidationError):
            self.consignment.save()
        with self.assertRaises(ValidationError):
            ConsignmentItem.objects.create(consignment=self.consignment, product=self.product,
                                           quantity=1, unit_price=Decimal('19.90'))

    def test_sent_price_and_name_survive_product_changes(self):
        send_consignment(self.consignment)
        self.product.name = 'Novo nome'
        self.product.sale_price = Decimal('39.90')
        self.product.save()
        self.item.refresh_from_db()
        self.assertEqual(self.item.product_name, 'Brinco')
        self.assertEqual(self.item.unit_price, Decimal('19.90'))
        self.item.unit_price = Decimal('39.90')
        with self.assertRaises(ValidationError):
            self.item.save()

    def test_database_constraints_block_bypassed_validation(self):
        for values in [{'stock_quantity': -1}, {'sale_price': Decimal('-0.01')}]:
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                Product.objects.filter(pk=self.product.pk).update(**values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConsignmentItem.objects.filter(pk=self.item.pk).update(sold_quantity=3, returned_quantity=2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Consignment.objects.filter(pk=self.consignment.pk).update(due_date=self.today - timedelta(days=1))

    def test_overdue_only_applies_to_sent_consignments(self):
        self.consignment.sent_date = self.today - timedelta(days=3)
        self.consignment.due_date = self.today - timedelta(days=1)
        self.consignment.save()
        self.assertFalse(self.consignment.is_overdue)
        send_consignment(self.consignment)
        self.assertTrue(self.consignment.is_overdue)

    def test_demo_refuses_existing_business_data(self):
        with self.assertRaises(CommandError):
            call_command('seed_demo', stdout=StringIO())


class DemoCommandTests(TestCase):
    def test_demo_is_consistent_and_explicitly_fictional(self):
        call_command('seed_demo', stdout=StringIO())
        self.assertEqual(Product.objects.count(), 10)
        self.assertEqual(Client.objects.count(), 5)
        self.assertEqual(Consignment.objects.count(), 5)
        self.assertTrue(Consignment.objects.filter(status='sent', due_date__lt=timezone.localdate()).exists())
        self.assertTrue(Consignment.objects.filter(status='closed').exists())
        self.assertTrue(Consignment.objects.filter(status='draft').exists())
        for client in Client.objects.all():
            self.assertIn('FICTÍCIOS', client.notes)
        for product in Product.objects.all():
            self.assertEqual(product.stock_quantity, sum(product.stock_movements.values_list('quantity', flat=True)))
        for consignment in Consignment.objects.all():
            self.assertGreaterEqual(consignment.pending_quantity, 0)
            self.assertGreaterEqual(consignment.balance, Decimal('0.00'))


class SQLiteConcurrencyTests(SimpleTestCase):
    def test_two_simultaneous_shipments_cannot_oversell(self):
        # File-backed SQLite waits for IMMEDIATE transactions; Django's shared
        # in-memory test database has different locking semantics. An isolated
        # process exercises the actual file-backed behavior without touching
        # the user's database or changing the test runner's connections.
        script = textwrap.dedent('''
            import os, queue, tempfile, threading
            from pathlib import Path
            from decimal import Decimal
            with tempfile.TemporaryDirectory(prefix='melo-concurrency-') as temporary:
                os.environ['MELO_DATA_DIR'] = temporary
                os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
                from django.conf import settings
                settings.DATABASES = {'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': str(Path(temporary) / 'test.sqlite3'),
                    'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE'},
                }}
                import django
                django.setup()
                from django.core.management import call_command
                from django.core.exceptions import ValidationError
                from django.db import connections
                from django.utils import timezone
                from core.models import Category, Client, Consignment, ConsignmentItem, Product, StockMovement
                from core.services import send_consignment
                call_command('migrate', verbosity=0)
                category = Category.objects.create(name='Teste')
                client = Client.objects.create(name='Cliente de teste')
                product = Product.objects.create(sku='T01', name='Peca de teste', category=category,
                    sale_price=Decimal('10.00'), stock_quantity=3)
                ids = []
                for _ in range(2):
                    record = Consignment.objects.create(client=client,
                        sent_date=timezone.localdate(), due_date=timezone.localdate())
                    ConsignmentItem.objects.create(consignment=record, product=product,
                        quantity=2, unit_price=Decimal('10.00'))
                    ids.append(record.pk)
                start = threading.Barrier(2)
                results = queue.Queue()
                def worker(record_id):
                    try:
                        start.wait(timeout=10)
                        send_consignment(Consignment(pk=record_id))
                        results.put('sent')
                    except ValidationError:
                        results.put('insufficient')
                    except Exception as error:
                        results.put(type(error).__name__ + ': ' + str(error))
                    finally:
                        connections.close_all()
                threads = [threading.Thread(target=worker, args=(record_id,), daemon=True) for record_id in ids]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=25)
                assert not any(thread.is_alive() for thread in threads), 'Concurrent shipment timed out'
                outcomes = sorted([results.get_nowait(), results.get_nowait()])
                assert outcomes == ['insufficient', 'sent'], outcomes
                product.refresh_from_db()
                assert product.stock_quantity == 1, product.stock_quantity
                assert StockMovement.objects.count() == 1
                assert Consignment.objects.filter(status='sent').count() == 1
                assert Consignment.objects.filter(status='draft').count() == 1
                connections.close_all()
        ''')
        result = subprocess.run([sys.executable, '-c', script], cwd=settings.BASE_DIR,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
