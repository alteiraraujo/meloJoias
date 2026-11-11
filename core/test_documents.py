from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sqlite3
import zipfile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client as Browser, override_settings
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfWriter

from .documents import prepare_signed_document, MAX_PDF_SIZE
from .models import Client, Consignment, StockMovement


def pdf_bytes(encrypted=False, empty=False):
    writer = PdfWriter()
    if not empty:
        writer.add_blank_page(width=595, height=842)
    if encrypted:
        writer.encrypt('senha')
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def upload(content=None, name='assinado.pdf'):
    return SimpleUploadedFile(name, pdf_bytes() if content is None else content, content_type='application/pdf')


class SignedDocumentTests(TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory(prefix='melo-pdf-tests-')
        self.addCleanup(self.folder.cleanup)
        self.override = override_settings(MEDIA_ROOT=Path(self.folder.name) / 'media')
        self.override.enable()
        self.addCleanup(self.override.disable)
        reseller = Client.objects.create(name='Revendedora do PDF')
        self.consignment = Consignment.objects.create(client=reseller, due_date=timezone.localdate())
        self.url = reverse('consignment_document_upload', args=[self.consignment.pk])
        self.document_url = reverse('consignment_document', args=[self.consignment.pk])

    def test_upload_open_download_preserve_original_bytes(self):
        original = pdf_bytes()
        response = self.client.post(self.url, {'signed_document': upload(original)})
        self.assertRedirects(response, reverse('consignment_detail', args=[self.consignment.pk]))
        self.consignment.refresh_from_db()
        self.assertTrue(self.consignment.signed_document.name.startswith('signed-documents/'))
        self.assertIsNotNone(self.consignment.signed_document_uploaded_at)
        self.assertEqual(Path(self.consignment.signed_document.path).read_bytes(), original)
        with override_settings(DEBUG=False):
            for suffix, disposition in [('', 'inline'), ('?download=1', 'attachment')]:
                response = self.client.get(self.document_url + suffix)
                self.assertEqual(response['Content-Type'], 'application/pdf')
                self.assertTrue(response['Content-Disposition'].startswith(disposition))
                self.assertEqual(b''.join(response.streaming_content), original)
                response.close()
        self.assertFalse(StockMovement.objects.exists())
        self.assertEqual(self.consignment.status, 'draft')

    def test_replacement_requires_confirmation_and_preserves_previous_file(self):
        self.client.post(self.url, {'signed_document': upload()})
        self.consignment.refresh_from_db()
        old_name = self.consignment.signed_document.name
        old_path = Path(self.consignment.signed_document.path)
        response = self.client.post(self.url, {'signed_document': upload()})
        self.assertContains(response, 'Confirme a substituição')
        self.consignment.refresh_from_db()
        self.assertEqual(self.consignment.signed_document.name, old_name)
        self.client.post(self.url, {'signed_document': upload(), 'replace_document': 'on'})
        self.consignment.refresh_from_db()
        self.assertNotEqual(self.consignment.signed_document.name, old_name)
        self.assertTrue(old_path.is_file())

    def test_invalid_upload_does_not_replace_current_pdf(self):
        self.client.post(self.url, {'signed_document': upload()})
        self.consignment.refresh_from_db()
        original = self.consignment.signed_document.name
        for file in [upload(b'<html>no PDF</html>'), upload(b'%PDF-1.7\ntruncated'),
                     upload(pdf_bytes(encrypted=True)), upload(pdf_bytes(empty=True)), upload(name='fake.txt')]:
            response = self.client.post(self.url, {'signed_document': file, 'replace_document': 'on'})
            self.assertTrue(response.context['document_form'].errors)
            self.consignment.refresh_from_db()
            self.assertEqual(self.consignment.signed_document.name, original)
        large = upload()
        large.size = MAX_PDF_SIZE + 1
        with self.assertRaisesMessage(ValidationError, '20 MB'):
            prepare_signed_document(large)

    def test_missing_file_missing_upload_csrf_and_method(self):
        self.assertEqual(self.client.get(self.document_url).status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(Browser(enforce_csrf_checks=True).post(self.url, {'signed_document': upload()}).status_code, 403)
        self.assertTrue(self.client.post(self.url, {}).context['document_form'].errors)
        self.client.post(self.url, {'signed_document': upload()})
        self.consignment.refresh_from_db()
        Path(self.consignment.signed_document.path).unlink()
        self.assertEqual(self.client.get(self.document_url).status_code, 404)

    def test_attachment_allowed_after_finalization_without_changing_status(self):
        for status in ('sent', 'closed', 'cancelled'):
            Consignment.objects.filter(pk=self.consignment.pk).update(status=status)
            self.assertEqual(self.client.post(self.url, {'signed_document': upload(), 'replace_document': 'on'}).status_code, 302)
            self.consignment.refresh_from_db()
            self.assertEqual(self.consignment.status, status)

    def test_backup_includes_pdf_without_product_photos(self):
        from scripts.backup import create_backup, BackupError
        self.client.post(self.url, {'signed_document': upload()})
        self.consignment.refresh_from_db()
        snapshot = Path(self.folder.name) / 'snapshot.sqlite3'
        with sqlite3.connect(snapshot) as db:
            db.execute('CREATE TABLE core_consignment (signed_document TEXT)')
            db.execute('INSERT INTO core_consignment VALUES (?)', [self.consignment.signed_document.name])
        db.close()
        with patch('scripts.backup.create_database_backup', return_value=snapshot), override_settings(DEMO_MODE=False):
            archive = create_backup()
            with zipfile.ZipFile(archive) as bundle:
                self.assertIn('data/melo.sqlite3', bundle.namelist())
                self.assertEqual(bundle.read('data/media/' + self.consignment.signed_document.name),
                                 Path(self.consignment.signed_document.path).read_bytes())
            Path(self.consignment.signed_document.path).unlink()
            with self.assertRaises(BackupError):
                create_backup()
