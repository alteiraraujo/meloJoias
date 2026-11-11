"""Validate PDFs without rewriting bytes, preserving any digital signatures."""
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from pypdf import PdfReader
from pypdf.errors import PyPdfError


MAX_PDF_SIZE = 20 * 1024 * 1024


def prepare_signed_document(upload):
    if Path(upload.name).suffix.lower() != '.pdf':
        raise ValidationError('Escolha um arquivo PDF.')
    if upload.size > MAX_PDF_SIZE:
        raise ValidationError('O PDF deve ter no máximo 20 MB.')
    upload.seek(0)
    content = upload.read(MAX_PDF_SIZE + 1)
    if len(content) > MAX_PDF_SIZE:
        raise ValidationError('O PDF deve ter no máximo 20 MB.')
    if not content.startswith(b'%PDF-'):
        raise ValidationError('O arquivo não é um PDF válido.')
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise ValidationError('Envie um PDF sem senha ou criptografia.')
        if not len(reader.pages):
            raise ValidationError('O PDF precisa conter ao menos uma página.')
    except (PyPdfError, OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError) as exc:
        raise ValidationError('Não foi possível ler o PDF. Confira o arquivo e tente novamente.') from exc
    return SimpleUploadedFile(f'{uuid4().hex}.pdf', content, content_type='application/pdf')
