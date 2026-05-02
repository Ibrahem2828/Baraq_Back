import requests
from django.conf import settings

from .exceptions import (
    AIServiceAuthenticationError,
    AIServiceBadResponseError,
    AIServiceDisabledError,
    AIServiceError,
    AIServiceTimeoutError,
)


class AIServiceClient:
    def __init__(
        self,
        base_url=None,
        api_key=None,
        timeout_seconds=None,
        verify_ssl=None,
        retry_count=None,
        session=None,
    ):
        self.base_url = (base_url or settings.AI_SERVICE_BASE_URL or '').rstrip('/')
        self.api_key = api_key or settings.AI_SERVICE_API_KEY
        self.timeout_seconds = timeout_seconds or settings.AI_SERVICE_TIMEOUT_SECONDS
        self.verify_ssl = (
            settings.AI_SERVICE_VERIFY_SSL if verify_ssl is None else verify_ssl
        )
        self.retry_count = (
            settings.AI_SERVICE_RETRY_COUNT if retry_count is None else retry_count
        )
        self.session = session or requests.Session()

    def is_enabled(self):
        return bool(settings.AI_SERVICE_ENABLED)

    def _build_url(self, endpoint):
        normalized_endpoint = endpoint if endpoint.startswith('/') else f'/{endpoint}'
        return f'{self.base_url}{normalized_endpoint}'

    def _build_headers(self):
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers

    def request(self, endpoint, payload=None, method='POST'):
        if not self.is_enabled():
            raise AIServiceDisabledError('AI service integration is disabled.')
        if not self.base_url:
            raise AIServiceBadResponseError('AI service base URL is not configured.')

        url = self._build_url(endpoint)
        request_kwargs = {
            'method': method.upper(),
            'url': url,
            'headers': self._build_headers(),
            'timeout': self.timeout_seconds,
            'verify': self.verify_ssl,
        }
        if payload is not None and method.upper() != 'GET':
            request_kwargs['json'] = payload

        for attempt in range(self.retry_count + 1):
            try:
                response = self.session.request(**request_kwargs)
            except requests.Timeout as exc:
                if attempt >= self.retry_count:
                    raise AIServiceTimeoutError('AI service request timed out.') from exc
                continue
            except requests.RequestException as exc:
                if attempt >= self.retry_count:
                    raise AIServiceError('Unable to reach the AI service.') from exc
                continue

            if response.status_code in {401, 403}:
                raise AIServiceAuthenticationError(
                    'AI service authentication failed.'
                )
            if response.status_code < 200 or response.status_code >= 300:
                raise AIServiceBadResponseError(
                    'AI service returned an unsuccessful response.'
                )

            try:
                return response.json()
            except ValueError as exc:
                raise AIServiceBadResponseError(
                    'AI service returned invalid JSON.'
                ) from exc

        raise AIServiceError('Unable to reach the AI service.')

    def health_check(self):
        return self.request('/health', method='GET')
