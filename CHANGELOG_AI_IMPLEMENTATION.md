# AI Implementation Change Log

## Added

- New `apps.ai_platform` Django application.
- Multi-provider adapters and routing.
- Prompt registry and versioned output schemas.
- AI request/output/feedback/data governance models.
- RAG and optional embedding retrieval.
- Asynchronous processing via Celery and Redis.
- Domain materialization for Fahes and Khota.
- Backend-authoritative analytics for Rasheed.
- User feedback, consent, anonymization, and human review.
- Dataset export and evaluation foundation.
- Cache reuse with source-version-aware hashes.
- Per-user daily AI throttle and atomic monthly subscription usage.
- Privacy deletion, consent revocation, and retention purge.
- AI platform admin screens and tests.

## Changed

- Project settings include AI provider, queue, embedding, privacy, and retention configuration.
- Project URLs expose `/api/ai/`.
- Docker Compose includes a Celery worker and Redis health checks.
- Gemini adapter omits sampling parameters for current stable Gemini 3.6-style models.

## Safety decisions

- No API keys in mobile code.
- Mock provider disabled by default.
- Phase-two tasks disabled by default.
- No automatic fine-tuning.
- Negative feedback without a corrected output is not accepted as supervised truth.
- User deletion overrides previous dataset consent.
