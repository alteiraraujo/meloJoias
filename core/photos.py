"""Normalize uploaded product photos before storing them on the local disk."""
from io import BytesIO
from uuid import uuid4
import warnings

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError


def prepare_photo(upload):
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError('A foto deve ter no máximo 5 MB.')
    try:
        upload.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload) as original:
                if original.format not in {'JPEG', 'PNG', 'WEBP'}:
                    raise ValidationError('Escolha uma foto JPG, PNG ou WebP.')
                if original.width * original.height > 20_000_000:
                    raise ValidationError('A foto deve ter no máximo 20 megapixels.')
                original.load()
                photo = ImageOps.exif_transpose(original)
                photo.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                rgba = photo.convert('RGBA')
                clean = Image.new('RGB', rgba.size, 'white')
                clean.paste(rgba, mask=rgba.getchannel('A'))
                output = BytesIO()
                clean.save(output, format='JPEG', quality=88, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValidationError('Não foi possível ler a imagem. Escolha uma foto JPG, PNG ou WebP válida.')
    return SimpleUploadedFile(f'{uuid4().hex}.jpg', output.getvalue(), content_type='image/jpeg')
