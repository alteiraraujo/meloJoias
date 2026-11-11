from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sqlite3
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Category, Product
from .photos import prepare_photo
from django.core.exceptions import ValidationError


def image_upload(name='jewel.png', size=(64, 48)):
    output = BytesIO()
    Image.new('RGBA', size, (210, 185, 110, 220)).save(output, 'PNG')
    return SimpleUploadedFile(name, output.getvalue(), content_type='image/png')


class ProductPhotoTests(TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory(prefix='melo-photo-tests-')
        self.addCleanup(self.folder.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=Path(self.folder.name) / 'media')
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.category = Category.objects.create(name='Joias')

    def data(self, **kwargs):
        return {'sku': 'PHOTO-01', 'name': 'Anel com foto', 'category': self.category.pk,
                'sale_price': '59,90', 'minimum_stock': 2, 'active': 'on', 'initial_stock': 4, **kwargs}

    def create_product(self):
        response = self.client.post(reverse('entity_create', args=['products']), self.data(photo=image_upload()))
        self.assertEqual(response.status_code, 302)
        return Product.objects.get(sku='PHOTO-01')

    def test_upload_optimized_photo_and_serve_without_debug(self):
        product = self.create_product()
        self.assertTrue(product.photo.name.startswith('products/'))
        self.assertTrue(product.photo.name.endswith('.jpg'))
        with Image.open(product.photo.path) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertEqual(image.mode, 'RGB')
        with override_settings(DEBUG=False):
            response = self.client.get(product.photo.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/jpeg')
            self.assertTrue(b''.join(response.streaming_content).startswith(b'\xff\xd8'))
            response.close()
        self.assertContains(self.client.get(reverse('entity_list', args=['products'])), product.photo.url)
        self.assertContains(self.client.get(reverse('entity_edit', args=['products', product.pk])), 'product-photo-preview')
        self.assertEqual(self.client.get('/media/unknown.jpg').status_code, 404)
        self.assertEqual(self.client.get('/media/../.secret_key').status_code, 404)

    def test_keep_replace_and_clear_without_changing_stock_or_ean(self):
        product = self.create_product()
        old_name, code = product.photo.name, product.ean13
        url = reverse('entity_edit', args=['products', product.pk])
        self.assertEqual(self.client.post(url, self.data(name='Nome editado')).status_code, 302)
        product.refresh_from_db()
        self.assertEqual(product.photo.name, old_name)
        self.assertEqual(self.client.post(url, self.data(photo=image_upload())).status_code, 302)
        product.refresh_from_db()
        self.assertNotEqual(product.photo.name, old_name)
        self.assertEqual(self.client.post(url, self.data(**{'photo-clear': 'on'})).status_code, 302)
        product.refresh_from_db()
        self.assertFalse(product.photo)
        self.assertEqual(product.stock_quantity, 4)
        self.assertEqual(product.ean13, code)

    def test_bad_files_are_rejected_and_existing_photo_survives(self):
        product = self.create_product()
        original = product.photo.name
        url = reverse('entity_edit', args=['products', product.pk])
        bad = SimpleUploadedFile('photo.jpg', b'<svg onload="alert(1)"></svg>', content_type='image/jpeg')
        response = self.client.post(url, self.data(photo=bad))
        self.assertEqual(response.status_code, 200)
        self.assertIn('photo', response.context['form'].errors)
        self.assertEqual(response.context['photo_preview_url'], product.photo.url)
        product.refresh_from_db()
        self.assertEqual(product.photo.name, original)
        huge = image_upload()
        huge.size = 5 * 1024 * 1024 + 1
        with self.assertRaisesMessage(ValidationError, '5 MB'):
            prepare_photo(huge)

    def test_resize_and_strip_exif(self):
        image = Image.new('RGB', (1800, 800), 'white')
        exif = image.getexif()
        exif[274] = 6
        exif[315] = 'Private metadata'
        output = BytesIO()
        image.save(output, 'JPEG', exif=exif)
        prepared = prepare_photo(SimpleUploadedFile('rotated.jpg', output.getvalue()))
        with Image.open(prepared) as result:
            self.assertEqual(result.height, 1600)
            self.assertLess(result.width, result.height)
            self.assertEqual(len(result.getexif()), 0)

    def test_backup_contains_database_and_referenced_photo(self):
        from scripts.backup import create_backup, BackupError
        product = self.create_product()
        snapshot = Path(self.folder.name) / 'snapshot.sqlite3'
        with sqlite3.connect(snapshot) as db:
            db.execute('CREATE TABLE core_product (photo TEXT)')
            db.execute('INSERT INTO core_product VALUES (?)', [product.photo.name])
        db.close()
        with patch('scripts.backup.create_database_backup', return_value=snapshot), override_settings(DEMO_MODE=False):
            archive = create_backup()
            with zipfile.ZipFile(archive) as bundle:
                self.assertIn('data/melo.sqlite3', bundle.namelist())
                name = 'data/media/' + product.photo.name
                self.assertEqual(bundle.read(name), Path(product.photo.path).read_bytes())
            Path(product.photo.path).unlink()
            with self.assertRaises(BackupError):
                create_backup()
