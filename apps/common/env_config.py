"""Pure, unit-testable helpers for resolving environment-driven settings.

Extracted out of ``config/settings.py`` so a renamed or duplicated env var
(e.g. a stray ``DJANGO_CSRF_TRUSTED_ORIGINS`` next to the real
``CSRF_TRUSTED_ORIGINS``) fails a fast, explicit test instead of silently
falling back to a wrong default in production.
"""
from __future__ import annotations


def resolve_list_setting(env, primary_key, *, fallback_keys=(), default=None):
    """Read a comma-separated list setting from ``primary_key``.

    If ``primary_key`` is unset or empty, raise on any of ``fallback_keys``
    being set instead of silently ignoring them -- a same-purpose variable
    under the wrong name is a configuration bug, not a fallback source.
    """
    value = env.list(primary_key, default=[])
    if value:
        stray = [key for key in fallback_keys if env.str(key, default="")]
        if stray:
            raise ValueError(
                f"{primary_key} is set, but so is {stray[0]!r}, which is not read by "
                "this application. Merge its values into "
                f"{primary_key} and remove {stray[0]!r} to avoid silent misconfiguration."
            )
        return value

    for key in fallback_keys:
        if env.str(key, default=""):
            raise ValueError(
                f"{key!r} is set but is not a recognized setting name. "
                f"Rename it to {primary_key!r}."
            )

    return list(default or [])
