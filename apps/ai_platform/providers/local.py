from __future__ import annotations

from typing import Any

import requests

from .base import AIProviderError, BaseAIProvider, ProviderResult


class LocalProvider(BaseAIProvider):
    """OpenAI-compatible local/fine-tuned model endpoint.

    This adapter is intentionally generic so a future vLLM, TGI, Ollama proxy,
    or privately hosted fine-tuned deployment can be enabled without changing
    character pipelines or mobile clients.
    """

    provider_name = 'local'

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        base_url: str,
        timeout_seconds: int = 90,
    ):
        super().__init__(api_key=api_key, model_name=model_name, timeout_seconds=timeout_seconds)
        self.base_url = base_url.rstrip('/')

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model_name)

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        temperature: float = 0.2,
        max_output_tokens: int = 4000,
    ) -> ProviderResult:
        if not self.configured:
            raise AIProviderError('Local provider is not configured.', code='provider_not_configured')

        schema_instruction = (
            '\nReturn JSON only. It must satisfy this JSON Schema exactly:\n'
            f'{output_schema}'
        )
        payload = {
            'model': self.model_name,
            'messages': [
                {'role': 'system', 'content': system_prompt + schema_instruction},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': temperature,
            'max_tokens': max_output_tokens,
            'response_format': {'type': 'json_object'},
        }
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        try:
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AIProviderError(
                'Local provider request failed.',
                code='provider_network_error',
                retryable=True,
            ) from exc

        if response.status_code >= 400:
            retryable = response.status_code in {408, 409, 429} or response.status_code >= 500
            raise AIProviderError(
                f'Local provider returned HTTP {response.status_code}.',
                code=f'local_http_{response.status_code}',
                retryable=retryable,
            )

        try:
            raw = response.json()
        except ValueError as exc:
            raise AIProviderError('Local provider returned invalid JSON.', code='invalid_provider_response') from exc

        choices = raw.get('choices') or []
        if not choices:
            raise AIProviderError('Local provider returned no choices.', code='empty_provider_response')
        content = (choices[0].get('message') or {}).get('content')
        data = self.parse_json_content(content)
        usage = raw.get('usage') or {}
        return ProviderResult(
            data=data,
            raw_response=raw,
            provider_request_id=str(raw.get('id') or ''),
            input_tokens=int(usage.get('prompt_tokens') or 0),
            output_tokens=int(usage.get('completion_tokens') or 0),
            model_name=str(raw.get('model') or self.model_name),
        )
