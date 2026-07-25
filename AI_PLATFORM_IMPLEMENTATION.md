# Baraq AI Platform — Backend Implementation

## Purpose

This Django app implements the first safe production-oriented slice of Baraq's AI platform. It keeps deterministic educational logic inside backend domains and uses LLMs for grounded generation and explanation.

## Phase order

- Phase 1: Fahes, Khota, Rasheed.
- Phase 2: Kholasa, Sada; disabled by default through `AI_PLATFORM_PHASE_TWO_ENABLED`.

## Main architecture

```text
Mobile/Dashboard
    -> Django API
        -> ai_platform
            -> Prompt Registry
            -> RAG Retriever
            -> Backend Rules/Analytics
            -> Model Router
                -> OpenAI
                -> Gemini
                -> DeepSeek
                -> Local OpenAI-compatible endpoint
            -> Structured Output Validators
            -> Domain Materializers
            -> Feedback/Dataset Governance
```

## Key APIs

```text
GET    /api/ai/capabilities/
GET    /api/ai/requests/
POST   /api/ai/requests/
GET    /api/ai/requests/{public_id}/
POST   /api/ai/requests/{public_id}/cancel/
GET    /api/ai/outputs/{id}/
POST   /api/ai/outputs/{id}/feedback/
GET    /api/ai/privacy/
DELETE /api/ai/privacy/
POST   /api/ai/privacy/revoke-training-consent/
```

## Request task types

```text
fahes_generate_quiz
khota_generate_plan
rasheed_recommend
kholasa_summarize
sada_transcribe
```

## Environment settings

See `.env.example`. Important variables:

```text
AI_PLATFORM_PHASE_TWO_ENABLED
AI_PLATFORM_RUN_SYNCHRONOUS
AI_PLATFORM_QUEUE_FALLBACK_SYNCHRONOUS
AI_PLATFORM_ALLOW_MOCK
AI_PROVIDER_FALLBACK_ORDER
AI_OPENAI_API_KEY
AI_OPENAI_MODEL
AI_GEMINI_API_KEY
AI_GEMINI_MODEL
AI_DEEPSEEK_API_KEY
AI_DEEPSEEK_MODEL
AI_LOCAL_BASE_URL
AI_LOCAL_API_KEY
AI_LOCAL_MODEL
AI_EMBEDDING_PROVIDER
AI_OPENAI_EMBEDDING_MODEL
AI_PLATFORM_CACHE_COMPLETED_REQUESTS
AI_PLATFORM_DAILY_THROTTLE_RATE
AI_DATA_RETENTION_DAYS
CELERY_BROKER_URL
CELERY_RESULT_BACKEND
```

## Local execution outline

```bash
python manage.py migrate
python manage.py seed_ai_platform
celery -A config worker -l info
python manage.py runserver
```

For local synchronous development only:

```text
AI_PLATFORM_RUN_SYNCHRONOUS=True
AI_PLATFORM_ALLOW_MOCK=True
```

Never enable the mock provider in production.

## Dataset workflow

```text
AI request/output
    -> explicit request consent
    -> user feedback + result-level allow_training
    -> anonymization
    -> pending candidate
    -> human approve/reject in admin
    -> versioned JSONL export
    -> offline evaluation
    -> controlled fine-tuning/canary deployment
```

A negative rating alone is never used as a supervised training target. A corrected output or a helpful accepted output is required before candidate creation.

## Export approved dataset

```bash
python manage.py export_ai_training_dataset \
  --dataset-version dataset-YYYYMMDD \
  --output /secure/path/baraq-training.jsonl
```

## Retention

Preview deletion:

```bash
python manage.py purge_ai_data --days 180 --dry-run
```

Execute:

```bash
python manage.py purge_ai_data --days 180
```

Approved training candidates are skipped by the scheduled retention command. An explicit user privacy deletion removes the user's AI history and derived candidates.

## Current RAG behavior

- Source chunking and references are implemented.
- Lexical retrieval is the default.
- Optional OpenAI embeddings and cosine ranking are implemented.
- Vectors are currently stored in JSON for compatibility with the existing database.
- Production scale should migrate to PostgreSQL + pgvector with a dedicated migration and ANN index.

## Validation status

- Python AST/compile validation passed.
- Runtime Django checks and full tests require installing project dependencies and a database/Redis environment.
