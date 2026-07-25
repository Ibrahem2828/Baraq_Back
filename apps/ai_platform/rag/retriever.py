from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from apps.ai_platform.models import SourceChunk

from .chunking import ensure_source_chunks
from .embeddings import (
    EmbeddingsNotConfigured,
    cosine_similarity,
    embed_chunks,
    embed_query,
)


ARABIC_STOP_WORDS = {
    'من', 'إلى', 'في', 'على', 'عن', 'ما', 'هو', 'هي', 'هذا', 'هذه', 'ذلك', 'التي', 'الذي',
    'مع', 'أو', 'و', 'ثم', 'تم', 'كل', 'بعد', 'قبل', 'بين', 'كما', 'أن', 'إن', 'لا', 'لم',
}


def _tokens(value: str) -> list[str]:
    values = re.findall(r'[\w\u0600-\u06FF]{2,}', value.lower())
    return [value for value in values if value not in ARABIC_STOP_WORDS]


def _lexical_score(query_tokens: Counter[str], chunk: SourceChunk) -> float:
    if not query_tokens:
        return 1.0 / (1 + chunk.chunk_index)
    chunk_tokens = Counter(_tokens(chunk.chunk_text))
    overlap = sum(min(count, chunk_tokens.get(token, 0)) for token, count in query_tokens.items())
    return overlap / max(1, sum(query_tokens.values()))


def _rank(chunks: list[SourceChunk], query: str) -> list[SourceChunk]:
    query_tokens = Counter(_tokens(query))
    if query.strip():
        try:
            embed_chunks(chunks)
            query_vector, model_name = embed_query(query)
            vector_ranked = [
                chunk
                for chunk in chunks
                if chunk.embedding and chunk.embedding_model == model_name
            ]
            if vector_ranked:
                return sorted(
                    vector_ranked,
                    key=lambda item: (
                        cosine_similarity(query_vector, item.embedding),
                        _lexical_score(query_tokens, item),
                    ),
                    reverse=True,
                )
        except EmbeddingsNotConfigured:
            pass
    return sorted(
        chunks,
        key=lambda item: (_lexical_score(query_tokens, item), -item.chunk_index),
        reverse=True,
    )


def retrieve_for_source(source, *, query: str = '', limit: int = 12) -> list[SourceChunk]:
    chunks = ensure_source_chunks(source)
    return _rank(chunks, query)[:max(1, limit)]


def retrieve_for_collection(collection, *, query: str = '', limit: int = 16) -> list[SourceChunk]:
    candidates: list[SourceChunk] = []
    for source in collection.sources.filter(status='ready').exclude(extracted_text=''):
        candidates.extend(ensure_source_chunks(source))
    return _rank(candidates, query)[:max(1, limit)]


def format_chunks(chunks: Iterable[SourceChunk], *, max_chars: int = 50000) -> tuple[str, list[dict]]:
    parts: list[str] = []
    references: list[dict] = []
    used = 0
    for chunk in chunks:
        header = f'[source={chunk.source_id}; chunk={chunk.chunk_index}; page={chunk.page_number or "unknown"}]\n'
        value = header + chunk.chunk_text.strip()
        if used + len(value) > max_chars:
            break
        parts.append(value)
        references.append(
            {
                'source_id': chunk.source_id,
                'chunk_index': chunk.chunk_index,
                'page_number': chunk.page_number,
            }
        )
        used += len(value)
    return '\n\n'.join(parts), references
