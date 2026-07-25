from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.ai_platform.models import SourceChunk


class EmbeddingProvider(Protocol):
    model_name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class EmbeddingsNotConfigured(RuntimeError):
    pass


@dataclass(slots=True)
class OpenAIEmbeddingProvider:
    api_key: str
    model_name: str = 'text-embedding-3-small'
    timeout_seconds: int = 90
    base_url: str = 'https://api.openai.com/v1'

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key or not self.model_name:
            raise EmbeddingsNotConfigured('OpenAI embeddings are not configured.')
        if not texts:
            return []
        try:
            response = requests.post(
                f'{self.base_url}/embeddings',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                },
                json={'model': self.model_name, 'input': texts, 'encoding_format': 'float'},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise EmbeddingsNotConfigured('Embedding request failed.') from exc
        if response.status_code >= 400:
            raise EmbeddingsNotConfigured(
                f'Embedding provider returned HTTP {response.status_code}.'
            )
        raw = response.json()
        rows = sorted(raw.get('data') or [], key=lambda item: item.get('index', 0))
        vectors = [item.get('embedding') for item in rows]
        if len(vectors) != len(texts) or any(not isinstance(item, list) for item in vectors):
            raise EmbeddingsNotConfigured('Embedding provider returned an invalid vector set.')
        return vectors


def get_embedding_provider() -> EmbeddingProvider:
    provider = str(getattr(settings, 'AI_EMBEDDING_PROVIDER', '') or '').lower()
    if provider in {'', 'none', 'lexical'}:
        raise EmbeddingsNotConfigured('Vector embeddings are disabled.')
    if provider == 'openai':
        return OpenAIEmbeddingProvider(
            api_key=str(getattr(settings, 'AI_OPENAI_API_KEY', '') or ''),
            model_name=str(
                getattr(settings, 'AI_OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
                or 'text-embedding-3-small'
            ),
            timeout_seconds=int(getattr(settings, 'AI_PLATFORM_TIMEOUT_SECONDS', 90)),
        )
    raise EmbeddingsNotConfigured(f'Unsupported embedding provider: {provider}')


@transaction.atomic
def embed_chunks(chunks: list[SourceChunk], *, batch_size: int = 64) -> int:
    provider = get_embedding_provider()
    pending = [
        chunk
        for chunk in chunks
        if not chunk.embedding or chunk.embedding_model != provider.model_name
    ]
    updated = 0
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        vectors = provider.embed([chunk.chunk_text for chunk in batch])
        now = timezone.now()
        for chunk, vector in zip(batch, vectors, strict=True):
            chunk.embedding = vector
            chunk.embedding_model = provider.model_name
            chunk.updated_at = now
        SourceChunk.objects.bulk_update(batch, ['embedding', 'embedding_model', 'updated_at'])
        updated += len(batch)
    return updated


def embed_query(query: str) -> tuple[list[float], str]:
    provider = get_embedding_provider()
    vectors = provider.embed([query])
    return vectors[0], provider.model_name


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return -1.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return -1.0
    return dot / (left_norm * right_norm)
