from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class AIProviderError(RuntimeError):
    """Raised when an upstream model provider cannot complete a request."""

    def __init__(self, message: str, *, code: str = 'provider_error', retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(slots=True)
class ProviderResult:
    data: dict[str, Any]
    raw_response: dict[str, Any] = field(default_factory=dict)
    provider_request_id: str = ''
    input_tokens: int = 0
    output_tokens: int = 0
    model_name: str = ''


class BaseAIProvider:
    provider_name = 'base'

    def __init__(self, *, api_key: str, model_name: str, timeout_seconds: int = 90):
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model_name)

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        temperature: float = 0.2,
        max_output_tokens: int = 4000,
    ) -> ProviderResult:
        raise NotImplementedError

    @staticmethod
    def parse_json_content(content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        if not isinstance(content, str):
            raise AIProviderError('Provider returned a non-text response.', code='invalid_provider_response')

        candidate = content.strip()
        if candidate.startswith('```'):
            lines = candidate.splitlines()
            if lines and lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            candidate = '\n'.join(lines).strip()
            if candidate.lower().startswith('json'):
                candidate = candidate[4:].lstrip()
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise AIProviderError(
                'Provider response was not valid JSON.',
                code='invalid_json',
                retryable=True,
            ) from exc
        if not isinstance(value, dict):
            raise AIProviderError('Provider JSON root must be an object.', code='invalid_json_root')
        return value
