from __future__ import annotations

import hashlib
import hmac
import time

from django.conf import settings
from rest_framework.permissions import BasePermission


class HasInternalServiceKey(BasePermission):
    message = "Invalid internal service credential."

    def has_permission(self, request, view):
        expected = settings.AI_SERVICE_INTERNAL_API_KEY
        if not expected:
            return False
        supplied = request.headers.get("X-Baraq-Internal-Key", "")
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            supplied = authorization[7:]
        return bool(supplied) and hmac.compare_digest(supplied, expected)


def sign_payload(body: bytes, timestamp: str) -> str:
    secret = settings.AI_SERVICE_WEBHOOK_SECRET.encode("utf-8")
    return hmac.new(secret, timestamp.encode("utf-8") + b"." + body, hashlib.sha256).hexdigest()


def verify_webhook(request, body: bytes | None = None, tolerance_seconds: int = 300) -> bool:
    timestamp = request.headers.get("X-Baraq-Timestamp", "")
    signature = request.headers.get("X-Baraq-Signature", "")
    if not timestamp or not signature or not settings.AI_SERVICE_WEBHOOK_SECRET:
        return False
    try:
        if abs(int(time.time()) - int(timestamp)) > tolerance_seconds:
            return False
    except (TypeError, ValueError):
        return False
    raw_body = request.body if body is None else body
    expected = sign_payload(raw_body, timestamp)
    return hmac.compare_digest(signature, expected)
