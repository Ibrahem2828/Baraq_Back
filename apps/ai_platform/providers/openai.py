from __future__ import annotations

from typing import Any

import requests

from .base import AIProviderError, BaseAIProvider, ProviderResult


class OpenAIProvider(BaseAIProvider):
    provider_name = 'openai'
    base_url = 'https://api.openai.com/v1'

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
            raise AIProviderError('OpenAI is not configured.', code='provider_not_configured')

        payload = {
            'model': self.model_name,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': temperature,
            'max_completion_tokens': max_output_tokens,
            'response_format': {
                'type': 'json_schema',
                'json_schema': {
                    'name': 'baraq_ai_result',
                    'strict': True,
                    'schema': output_schema,
                },
            },
        }
        try:
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AIProviderError(
                'OpenAI request failed.', code='provider_network_error', retryable=True
            ) from exc

        if response.status_code >= 400:
            retryable = response.status_code in {408, 409, 429} or response.status_code >= 500
            raise AIProviderError(
                f'OpenAI returned HTTP {response.status_code}.',
                code=f'openai_http_{response.status_code}',
                retryable=retryable,
            )

        raw = response.json()
        choices = raw.get('choices') or []
        if not choices:
            raise AIProviderError('OpenAI returned no choices.', code='empty_provider_response')
        message = choices[0].get('message') or {}
        refusal = message.get('refusal')
        if refusal:
            raise AIProviderError(str(refusal), code='provider_refusal')
        data = self.parse_json_content(message.get('content'))
        usage = raw.get('usage') or {}
        return ProviderResult(
            data=data,
            raw_response=raw,
            provider_request_id=str(raw.get('id') or ''),
            input_tokens=int(usage.get('prompt_tokens') or 0),
            output_tokens=int(usage.get('completion_tokens') or 0),
            model_name=str(raw.get('model') or self.model_name),
        )
