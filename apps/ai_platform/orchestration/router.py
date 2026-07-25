from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.ai_platform.models import AIProvider, ModelDeployment
from apps.ai_platform.providers import (
    DeepSeekProvider,
    GeminiProvider,
    LocalProvider,
    MockProvider,
    OpenAIProvider,
)


@dataclass(frozen=True, slots=True)
class RoutedProvider:
    name: str
    model_name: str
    client: object
    input_cost_per_million: float = 0
    output_cost_per_million: float = 0


SUPPORTED_RUNTIME_PROVIDERS = {
    AIProvider.OPENAI,
    AIProvider.GEMINI,
    AIProvider.DEEPSEEK,
    AIProvider.LOCAL,
    AIProvider.MOCK,
}


def _settings_config(provider: str) -> tuple[str, str]:
    mapping = {
        AIProvider.OPENAI: ('AI_OPENAI_API_KEY', 'AI_OPENAI_MODEL'),
        AIProvider.GEMINI: ('AI_GEMINI_API_KEY', 'AI_GEMINI_MODEL'),
        AIProvider.DEEPSEEK: ('AI_DEEPSEEK_API_KEY', 'AI_DEEPSEEK_MODEL'),
        AIProvider.LOCAL: ('AI_LOCAL_API_KEY', 'AI_LOCAL_MODEL'),
    }
    if provider not in mapping:
        return '', ''
    key_setting, model_setting = mapping[provider]
    return str(getattr(settings, key_setting, '') or ''), str(getattr(settings, model_setting, '') or '')


def _build(provider: str, model_name: str = '') -> RoutedProvider | None:
    timeout = int(getattr(settings, 'AI_PLATFORM_TIMEOUT_SECONDS', 90))
    if provider not in SUPPORTED_RUNTIME_PROVIDERS:
        return None
    if provider == AIProvider.MOCK:
        if not getattr(settings, 'AI_PLATFORM_ALLOW_MOCK', False):
            return None
        client = MockProvider(api_key='mock', model_name='mock-v1', timeout_seconds=timeout)
        return RoutedProvider(provider, 'mock-v1', client)

    api_key, configured_model = _settings_config(provider)
    final_model = model_name or configured_model
    if provider == AIProvider.LOCAL:
        client = LocalProvider(
            api_key=api_key,
            model_name=final_model,
            base_url=str(getattr(settings, 'AI_LOCAL_BASE_URL', '') or ''),
            timeout_seconds=timeout,
        )
    else:
        classes = {
            AIProvider.OPENAI: OpenAIProvider,
            AIProvider.GEMINI: GeminiProvider,
            AIProvider.DEEPSEEK: DeepSeekProvider,
        }
        client = classes[provider](api_key=api_key, model_name=final_model, timeout_seconds=timeout)
    return RoutedProvider(provider, final_model, client)


def route_provider(*, task_type: str, requested_provider: str = AIProvider.AUTO) -> list[RoutedProvider]:
    if requested_provider != AIProvider.AUTO:
        candidate = _build(requested_provider)
        return [candidate] if candidate and candidate.client.configured else []

    deployments = list(ModelDeployment.objects.filter(is_active=True).order_by('priority', 'id'))
    routed: list[RoutedProvider] = []
    for deployment in deployments:
        if deployment.provider in {AIProvider.AUTO, AIProvider.MOCK} and deployment.provider != AIProvider.MOCK:
            continue
        if deployment.supported_tasks and task_type not in deployment.supported_tasks:
            continue
        provider = _build(deployment.provider, deployment.model_name)
        if provider is None or not provider.client.configured:
            continue
        routed.append(
            RoutedProvider(
                provider.name,
                provider.model_name,
                provider.client,
                float(deployment.input_cost_per_million),
                float(deployment.output_cost_per_million),
            )
        )

    if routed:
        return routed

    configured_order = list(
        getattr(settings, 'AI_PROVIDER_FALLBACK_ORDER', ['openai', 'gemini', 'deepseek', 'local'])
    )
    for provider_name in configured_order:
        if provider_name not in {
            AIProvider.OPENAI,
            AIProvider.GEMINI,
            AIProvider.DEEPSEEK,
            AIProvider.LOCAL,
        }:
            continue
        candidate = _build(provider_name)
        if candidate and candidate.client.configured:
            routed.append(candidate)
    if not routed:
        mock = _build(AIProvider.MOCK)
        if mock:
            routed.append(mock)
    return routed
