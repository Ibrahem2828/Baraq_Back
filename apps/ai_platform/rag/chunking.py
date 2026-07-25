from __future__ import annotations

import hashlib
import re

from django.db import transaction

from apps.ai_platform.models import SourceChunk


DEFAULT_CHUNK_CHARS = 2200
DEFAULT_OVERLAP_CHARS = 250


def normalize_text(text: str) -> str:
    text = text.replace('\x00', ' ')
    text = re.sub(r'\r\n?', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def split_text(text: str, *, chunk_chars: int = DEFAULT_CHUNK_CHARS, overlap_chars: int = DEFAULT_OVERLAP_CHARS) -> list[str]:
    clean = normalize_text(text)
    if not clean:
        return []
    chunks: list[str] = []
    cursor = 0
    length = len(clean)
    while cursor < length:
        end = min(cursor + chunk_chars, length)
        if end < length:
            boundary = max(clean.rfind('\n', cursor, end), clean.rfind('. ', cursor, end), clean.rfind('؟', cursor, end))
            if boundary > cursor + chunk_chars // 2:
                end = boundary + 1
        chunk = clean[cursor:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        cursor = max(end - overlap_chars, cursor + 1)
    return chunks


@transaction.atomic
def ensure_source_chunks(source, *, force: bool = False) -> list[SourceChunk]:
    if not force and source.ai_chunks.exists():
        return list(source.ai_chunks.all())
    source.ai_chunks.all().delete()
    chunks = split_text(source.extracted_text or '')
    objects = [
        SourceChunk(
            source=source,
            chunk_index=index,
            chunk_text=chunk,
            content_hash=hashlib.sha256(chunk.encode('utf-8')).hexdigest(),
            token_count=max(1, len(chunk) // 4),
        )
        for index, chunk in enumerate(chunks)
    ]
    SourceChunk.objects.bulk_create(objects)
    return list(source.ai_chunks.all())
