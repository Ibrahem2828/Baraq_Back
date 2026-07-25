from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', re.IGNORECASE)
PHONE_RE = re.compile(r'(?<!\d)(?:\+?\d[\d\s()\-]{6,}\d)(?!\d)')


def anonymize_text(value: str) -> str:
    value = EMAIL_RE.sub('[EMAIL_REDACTED]', value)
    value = PHONE_RE.sub('[PHONE_REDACTED]', value)
    return value


def anonymize_value(value: Any) -> Any:
    if isinstance(value, str):
        return anonymize_text(value)
    if isinstance(value, list):
        return [anonymize_value(item) for item in value]
    if isinstance(value, dict):
        blocked_keys = {'email', 'phone', 'phone_number', 'access_token', 'refresh_token', 'password'}
        return {
            key: ('[REDACTED]' if key.lower() in blocked_keys else anonymize_value(item))
            for key, item in value.items()
        }
    return value
