import mimetypes
from pathlib import Path

from django.conf import settings
from rest_framework.exceptions import ValidationError


ALLOWED_EXTENSIONS = {
    'pdf',
    'txt',
    'jpg',
    'jpeg',
    'png',
    'webp',
    'doc',
    'docx',
    'ppt',
    'pptx',
    'mp3',
    'm4a',
    'wav',
}

DANGEROUS_EXTENSIONS = {
    'exe',
    'sh',
    'bat',
    'cmd',
    'js',
    'html',
    'php',
    'py',
    'jar',
    'zip',
    'rar',
    '7z',
    'sql',
    'env',
}

EXTENSION_SOURCE_TYPES = {
    'pdf': 'pdf',
    'txt': 'text',
    'jpg': 'image',
    'jpeg': 'image',
    'png': 'image',
    'webp': 'image',
    'doc': 'document',
    'docx': 'document',
    'ppt': 'presentation',
    'pptx': 'presentation',
    'mp3': 'audio',
    'm4a': 'audio',
    'wav': 'audio',
}


def get_safe_extension(filename):
    extension = Path(filename or '').suffix.lower().lstrip('.')
    if not extension:
        raise ValidationError({'file': 'File extension is required.'})
    if extension in DANGEROUS_EXTENSIONS:
        raise ValidationError({'file': f'Files with .{extension} extension are not allowed.'})
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError({'file': f'Unsupported file extension .{extension}.'})
    return extension


def get_file_mime_type(file):
    content_type = getattr(file, 'content_type', '') or ''
    guessed_type, _encoding = mimetypes.guess_type(getattr(file, 'name', ''))
    return content_type or guessed_type or 'application/octet-stream'


def get_source_type_from_file(file):
    extension = get_safe_extension(getattr(file, 'name', ''))
    return EXTENSION_SOURCE_TYPES.get(extension, 'other')


def validate_student_source_file(file):
    if file is None:
        raise ValidationError({'file': 'File is required.'})

    size = getattr(file, 'size', 0) or 0
    if size <= 0:
        raise ValidationError({'file': 'File is empty.'})

    max_mb = getattr(settings, 'STUDENT_SOURCE_MAX_UPLOAD_MB', 25)
    max_bytes = max_mb * 1024 * 1024
    if size > max_bytes:
        raise ValidationError({'file': f'Maximum upload size is {max_mb}MB.'})

    extension = get_safe_extension(getattr(file, 'name', ''))
    mime_type = get_file_mime_type(file)
    source_type = EXTENSION_SOURCE_TYPES.get(extension, 'other')

    return {
        'extension': extension,
        'mime_type': mime_type,
        'source_type': source_type,
        'file_size': size,
        'original_filename': Path(getattr(file, 'name', '')).name,
    }
