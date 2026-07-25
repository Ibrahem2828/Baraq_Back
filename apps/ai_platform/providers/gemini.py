from __future__ import annotations

from typing import Any

import requests

from .base import AIProviderError, BaseAIProvider, ProviderResult


class GeminiProvider(BaseAIProvider):
    provider_name = 'gemini'
    base_url = 'https://generativelanguage.googleapis.com/v1beta'

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
            raise AIProviderError('Gemini is not configured.', code='provider_not_configured')
        generation_config = {
            'maxOutputTokens': max_output_tokens,
            'responseMimeType': 'application/json',
            'responseJsonSchema': output_schema,
        }
        # Gemini 3.6 Flash and later 3.x releases deprecate sampling
        # parameters. Omitting them keeps the adapter compatible with current
        # stable models while older models continue to use their defaults.
        if not self.model_name.startswith(('gemini-3.6-', 'gemini-3.5-flash-lite')):
            generation_config['temperature'] = temperature
        payload = {
            'systemInstruction': {'parts': [{'text': system_prompt}]},
            'contents': [{'role': 'user', 'parts': [{'text': user_prompt}]}],
            'generationConfig': generation_config,
        }
        try:
            response = requests.post(
                f'{self.base_url}/models/{self.model_name}:generateContent',
                params={'key': self.api_key},
                headers={'Content-Type': 'application/json'},
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AIProviderError(
                'Gemini request failed.', code='provider_network_error', retryable=True
            ) from exc
        if response.status_code >= 400:
            retryable = response.status_code in {408, 409, 429} or response.status_code >= 500
            raise AIProviderError(
                f'Gemini returned HTTP {response.status_code}.',
                code=f'gemini_http_{response.status_code}',
                retryable=retryable,
            )
        raw = response.json()
        candidates = raw.get('candidates') or []
        if not candidates:
            block_reason = (raw.get('promptFeedback') or {}).get('blockReason')
            raise AIProviderError(
                block_reason or 'Gemini returned no candidates.',
                code='provider_refusal' if block_reason else 'empty_provider_response',
            )
        parts = ((candidates[0].get('content') or {}).get('parts') or [])
        content = ''.join(str(part.get('text') or '') for part in parts)
        data = self.parse_json_content(content)
        usage = raw.get('usageMetadata') or {}
        return ProviderResult(
            data=data,
            raw_response=raw,
            provider_request_id=str(raw.get('responseId') or ''),
            input_tokens=int(usage.get('promptTokenCount') or 0),
            output_tokens=int(usage.get('candidatesTokenCount') or 0),
            model_name=str(raw.get('modelVersion') or self.model_name),
        )
