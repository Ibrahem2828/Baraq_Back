from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from django.conf import settings

from .security import sign_payload

logger = logging.getLogger(__name__)


class AIServiceError(RuntimeError):
    def __init__(self, message, *, code="ai_service_error", status_code=None, retryable=False):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


@dataclass(frozen=True)
class AIServiceResponse:
    data: dict
    status_code: int


class AIServiceClient:
    def __init__(self):
        self.base_url = settings.AI_SERVICE_BASE_URL.rstrip("/") + "/"
        self.timeout = settings.AI_SERVICE_TIMEOUT_SECONDS
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "User-Agent": "Baraq-Backend/1.0"})

    def _request(self, method, path, *, payload=None, idempotency_key=None):
        if not settings.AI_SERVICE_ENABLED:
            raise AIServiceError("AI service is disabled.", code="ai_service_disabled", status_code=503)
        method = method.upper()
        body = b"" if method == "GET" else json.dumps(payload or {}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-Baraq-Timestamp": timestamp,
            "X-Baraq-Signature": sign_payload(body, timestamp),
            "X-Baraq-Internal-Key": settings.AI_SERVICE_INTERNAL_API_KEY,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        url = urljoin(self.base_url, path.lstrip("/"))
        try:
            response = self.session.request(
                method,
                url,
                data=body or None,
                headers=headers,
                timeout=self.timeout,
                verify=settings.AI_SERVICE_VERIFY_SSL,
            )
        except requests.Timeout as exc:
            raise AIServiceError("AI service timeout.", code="ai_service_timeout", retryable=True) from exc
        except requests.RequestException as exc:
            raise AIServiceError("AI service is unavailable.", code="ai_service_unavailable", retryable=True) from exc
        try:
            data = response.json()
        except ValueError:
            data = {"message": response.text[:500]}
        if response.status_code >= 400:
            retryable = response.status_code in {408, 425, 429, 500, 502, 503, 504}
            raise AIServiceError(
                str(data.get("message") or data.get("detail") or "AI service request failed."),
                code=str(data.get("code") or "ai_service_error"),
                status_code=response.status_code,
                retryable=retryable,
            )
        return AIServiceResponse(data=data.get("data", data), status_code=response.status_code)

    def create_job(self, payload, idempotency_key):
        return self._request("POST", settings.AI_SERVICE_JOBS_PATH, payload=payload, idempotency_key=idempotency_key)

    def get_job(self, external_job_id):
        return self._request("GET", f"{settings.AI_SERVICE_JOBS_PATH.rstrip('/')}/{external_job_id}")

    def cancel_job(self, external_job_id):
        return self._request("POST", f"{settings.AI_SERVICE_JOBS_PATH.rstrip('/')}/{external_job_id}/cancel", payload={})

    def send_feedback(self, payload, idempotency_key):
        return self._request("POST", settings.AI_SERVICE_FEEDBACK_PATH, payload=payload, idempotency_key=idempotency_key)

    def health(self):
        return self._request("GET", settings.AI_SERVICE_HEALTH_PATH)
