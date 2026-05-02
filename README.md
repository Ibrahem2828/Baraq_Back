# Baraq Backend

Production-ready Django + Django REST Framework backend for the Baraq platform.

## Stack

- Python 3.12
- Django
- Django REST Framework
- Simple JWT
- PostgreSQL
- Docker and Docker Compose
- drf-spectacular

## Implemented Phases

### Phase 1

- Custom User model based on `email`
- JWT authentication
- Student profile setup
- Education stages and subjects
- User subject selection
- Django Admin foundation

### Phase 2: Khuta (خُطى) Study Planning

Khuta is the study-planning layer of Baraq. It is responsible for:

- creating study plans
- auto-generating daily tasks
- returning today view
- returning week view
- managing task progress
- logging progress events for future analytics and AI assistants
- preparing a mock AI generation path that can later be replaced by `ai_gateway`

### Phase 3: Fahis (فاحص) Quiz and Assessment Engine

Fahis is the assessment layer of Baraq. It is responsible for:

- creating user-owned quizzes
- generating initial mock questions for manual or AI-marked creation flows
- supporting `mcq`, `true_false`, and the initial `short_answer` structure
- starting quiz attempts
- receiving incremental or final answers
- grading answers automatically for `mcq` and `true_false`
- calculating score, percentage, and unanswered counts
- storing attempt history and result details
- logging quiz progress events for future analytics and AI assistants
- preparing a mock AI quiz generation path that can later be replaced by `apps.ai_gateway`

### Phase 3.5: Stabilization and MVP Readiness

Phase 3.5 is a stabilization pass before the project moves into heavier infrastructure and AI-related work. It is responsible for:

- adding a shared response helper layer for future endpoints
- standardizing API error payloads through a global DRF exception handler
- exposing system endpoints for health and project metadata
- seeding academic stages and subjects through a repeatable management command
- reviewing pagination, filtering, search, ordering, and permissions without breaking previous phases
- polishing Swagger tags and system documentation
- adding regression coverage for MVP-readiness scenarios

### Phase 3.6: AI Gateway Configuration

Phase 3.6 introduces a centralized AI gateway layer so future AI-enabled features only communicate through `apps.ai_gateway`. It is responsible for:

- reading AI service configuration from environment variables
- exposing a reusable HTTP client for the future external AI service
- defining stable request and response contracts for AI operations
- returning safe mock responses while `AI_SERVICE_ENABLED=false`
- exposing internal status and health endpoints for the gateway
- preparing `study_plans` and `quizzes` to use the centralized gateway for `generation_type="ai"`

## New Models in Phase 2

- `StudyPlan`
- `StudyTask`
- `StudyPlanProgressLog`

## New Models in Phase 3

- `Quiz`
- `Question`
- `Choice`
- `QuizAttempt`
- `StudentAnswer`
- `QuestionBankItem`
- `QuizProgressLog`

## New Utilities in Phase 3.5

- `apps.common.responses.success_response`
- `apps.common.responses.error_response`
- `apps.common.responses.validation_error_response`
- `apps.common.exceptions.custom_exception_handler`
- `python manage.py seed_academic_data`

## New Utilities in Phase 3.6

- `apps.ai_gateway.client.AIServiceClient`
- `apps.ai_gateway.services.generate_study_plan`
- `apps.ai_gateway.services.generate_quiz`
- `apps.ai_gateway.services.summarize_text`
- `apps.ai_gateway.services.transcribe_audio`
- `apps.ai_gateway.services.generate_recommendations`
- `apps.ai_gateway.services.ai_health_check`

## Local Setup

```powershell
cd backend
Copy-Item .env.example .env
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

If `DATABASE_URL` is not provided, the project falls back to SQLite for quick local checks. Production and Docker are expected to use PostgreSQL.

## AI Gateway Environment Variables

Add these values to `.env` for local and deployment environments:

```env
AI_SERVICE_ENABLED=false
AI_SERVICE_BASE_URL=http://localhost:8001
AI_SERVICE_API_KEY=change-me
AI_SERVICE_TIMEOUT_SECONDS=60
AI_SERVICE_VERIFY_SSL=true
AI_SERVICE_RETRY_COUNT=2
```

- `AI_SERVICE_ENABLED=false` keeps the backend in mock mode.
- When `AI_SERVICE_ENABLED=true`, requests are routed through `apps.ai_gateway.client.AIServiceClient`.
- The backend never exposes the configured API key in responses.

## Docker Setup

```powershell
cd backend
Copy-Item .env.example .env
docker compose up --build
docker compose exec web python manage.py createsuperuser
```

## Important Commands

```powershell
python manage.py makemigrations
python manage.py migrate
python manage.py seed_academic_data
python manage.py check
python manage.py test
python manage.py test apps.common.tests
python manage.py test apps.study_plans.tests
python manage.py test apps.quizzes.tests
python manage.py test apps.ai_gateway.tests
python manage.py test apps.common.tests apps.study_plans.tests apps.quizzes.tests
python manage.py runserver
```

## API Documentation

- Swagger UI: `/api/docs/`
- OpenAPI schema: `/api/schema/`

## Existing Phase 1 Endpoints

### Auth and Users

- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/refresh/`
- `GET /api/users/me/`
- `PATCH /api/users/me/`

### Students

- `POST /api/students/setup-profile/`
- `GET /api/students/profile/`
- `PATCH /api/students/profile/`

### Subjects

- `GET /api/education-stages/`
- `GET /api/subjects/`
- `GET /api/subjects/?education_stage=1`
- `POST /api/users/subjects/`
- `GET /api/users/subjects/`
- `DELETE /api/users/subjects/{id}/`

## Phase 2 Endpoints

### Study Plans

- `GET /api/study-plans/`
- `POST /api/study-plans/`
- `GET /api/study-plans/{id}/`
- `PATCH /api/study-plans/{id}/`
- `DELETE /api/study-plans/{id}/`
- `GET /api/study-plans/{id}/tasks/`
- `POST /api/study-plans/{id}/tasks/`
- `GET /api/study-plans/today/`
- `GET /api/study-plans/week/`
- `GET /api/study-plans/week/?start_date=2026-05-01`

### Study Tasks

- `GET /api/study-tasks/{id}/`
- `PATCH /api/study-tasks/{id}/`
- `DELETE /api/study-tasks/{id}/`
- `POST /api/study-tasks/{id}/complete/`
- `POST /api/study-tasks/{id}/skip/`
- `POST /api/study-tasks/{id}/reopen/`

## Phase 3 Endpoints

### Quizzes

- `GET /api/quizzes/`
- `POST /api/quizzes/`
- `GET /api/quizzes/{id}/`
- `PATCH /api/quizzes/{id}/`
- `DELETE /api/quizzes/{id}/`
- `POST /api/quizzes/{id}/start/`
- `POST /api/quizzes/{id}/archive/`

### Quiz Attempts

- `GET /api/quiz-attempts/`
- `GET /api/quiz-attempts/{id}/`
- `POST /api/quiz-attempts/{id}/answer/`
- `POST /api/quiz-attempts/{id}/submit/`
- `GET /api/quiz-attempts/{id}/result/`
- `POST /api/quiz-attempts/{id}/abandon/`

### Question Bank

- `GET /api/question-bank/`
- `GET /api/question-bank/{id}/`

## Phase 3.5 Endpoints

- `GET /api/health/`
- `GET /api/meta/`

## Phase 3.6 Endpoints

- `GET /api/ai-gateway/status/`
- `GET /api/ai-gateway/health/`

## Filters, Search, and Ordering

`GET /api/study-plans/` supports:

- `status`
- `subject`
- `start_date`
- `end_date`
- `difficulty_level`
- `generation_type`
- `search` on `title` and `goal`
- `ordering` with `created_at`, `start_date`, `end_date`

`GET /api/quizzes/` supports:

- `subject`
- `difficulty_level`
- `quiz_type`
- `generation_type`
- `status`
- `search` on `title` and `topic`
- `ordering` with `created_at`, `questions_count`

`GET /api/quiz-attempts/` supports:

- `quiz`
- `status`
- `subject`

`GET /api/question-bank/` supports:

- `subject`
- `difficulty_level`
- `question_type`

`GET /api/subjects/` supports:

- `education_stage`
- `grade_level`
- `is_active`

All paginated list endpoints use the shared page-number pagination layer with:

- default `page_size=20`
- optional `page_size` query parameter
- `max_page_size=100`

## Week View Rule

If `start_date` is not provided to `/api/study-plans/week/`, the API starts from the current week Monday and returns a 7-day window.

## Request Examples

### Create a Study Plan

```http
POST /api/study-plans/
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "title": "Math Review Plan",
  "description": "Preparation for the final exam",
  "subject": 1,
  "start_date": "2026-05-01",
  "end_date": "2026-05-05",
  "daily_study_minutes": 120,
  "goal": "Review the main chapters and solve exercises",
  "difficulty_level": "medium",
  "generation_type": "manual"
}
```

### Add a Manual Task to a Plan

```http
POST /api/study-plans/3/tasks/
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "title": "Solve chapter one exercises",
  "description": "Solve 20 practice questions",
  "task_date": "2026-05-02",
  "estimated_minutes": 60,
  "priority": "high",
  "order": 1
}
```

### Mark a Task as Completed

```http
POST /api/study-tasks/10/complete/
Authorization: Bearer <access_token>
```

### Create a Quiz

```http
POST /api/quizzes/
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "subject": 1,
  "title": "Newton Laws Quiz",
  "description": "Short practice assessment",
  "topic": "Newton Laws",
  "difficulty_level": "medium",
  "quiz_type": "practice",
  "generation_type": "manual",
  "questions_count": 5,
  "time_limit_minutes": 15,
  "question_types": ["mcq", "true_false"]
}
```

### Start a Quiz Attempt

```http
POST /api/quizzes/1/start/
Authorization: Bearer <access_token>
```

### Submit a Quiz Attempt

```http
POST /api/quiz-attempts/1/submit/
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "answers": [
    {
      "question": 1,
      "selected_choice": 3
    },
    {
      "question": 2,
      "selected_choice": 6
    }
  ]
}
```

### Result Response Shape

```json
{
  "attempt": {
    "id": 1,
    "status": "submitted",
    "score": "4.00",
    "max_score": "5.00",
    "percentage": "80.00",
    "correct_answers_count": 4,
    "wrong_answers_count": 1,
    "unanswered_count": 0
  },
  "quiz": {
    "id": 1,
    "title": "Newton Laws Quiz"
  },
  "answers": [
    {
      "question_id": 1,
      "text": "Question 1",
      "correct_choice": {
        "id": 3,
        "text": "Correct answer",
        "is_correct": true,
        "order": 1
      },
      "selected_choice": {
        "id": 3,
        "text": "Correct answer",
        "is_correct": true,
        "order": 1
      },
      "is_correct": true,
      "points_awarded": "1.00"
    }
  ],
  "recommendations": [
    "Review the questions you missed.",
    "Retry the quiz after reviewing the explanations."
  ]
}
```

### System Health Response

```json
{
  "success": true,
  "message": "Health check completed successfully",
  "data": {
    "status": "ok",
    "service": "baraq_backend",
    "database": "ok",
    "version": "phase-3.5"
  }
}
```

### AI Gateway Status Response

```json
{
  "success": true,
  "message": "AI Gateway status",
  "data": {
    "enabled": false,
    "base_url_configured": true,
    "mode": "mock",
    "available_operations": [
      "generate_study_plan",
      "generate_quiz",
      "summarize_text",
      "transcribe_audio",
      "generate_recommendations"
    ]
  }
}
```

### Example Today Response Shape

```json
{
  "date": "2026-05-01",
  "summary": {
    "total_tasks": 2,
    "completed_tasks": 1,
    "pending_tasks": 1,
    "total_estimated_minutes": 120
  },
  "tasks": [
    {
      "id": 10,
      "title": "Review a topic in Mathematics",
      "description": "Review chapters and solve exercises",
      "task_date": "2026-05-01",
      "estimated_minutes": 60,
      "priority": "medium",
      "status": "pending",
      "order": 1,
      "completed_at": null,
      "plan": {
        "id": 3,
        "title": "Math Review Plan",
        "status": "active",
        "subject": {
          "id": 1,
          "name": "Mathematics",
          "education_stage": 1,
          "education_stage_name": "Secondary",
          "grade_level": "Grade 12",
          "description": "Core subject",
          "is_active": true
        }
      }
    }
  ]
}
```

## Notes for Phase 2

- Business logic is intentionally placed in `apps/study_plans/services.py`.
- Reusable query logic is placed in `apps/study_plans/selectors.py`.
- The AI flow is not real yet.
- `create_ai_plan` uses a mock placeholder and stores `ai_request_id`.
- There is a clear `TODO` in `services.py` to replace this with a real `ai_gateway` integration later.

## Notes for Phase 3

- Business logic is intentionally placed in `apps/quizzes/services.py`.
- Reusable query logic is placed in `apps/quizzes/selectors.py`.
- Correct answers are intentionally hidden from quiz detail and in-progress attempt responses.
- The real AI quiz generation flow is not enabled yet.
- `generate_ai_quiz_mock` is a temporary placeholder and stores `ai_request_id`.
- There is a clear `TODO` in `services.py` to replace this with a real `apps.ai_gateway` integration later.
- `QuestionBankItem` is read-only over API in this phase and remains manageable from Django Admin.

## Notes for Phase 3.5

- Successful business endpoints from Phases 1, 2, and 3 keep their existing response shapes for compatibility.
- New system endpoints use the shared response helper envelope.
- API errors now pass through `apps.common.exceptions.custom_exception_handler`.
- Validation responses remain readable and preserve field-level keys to reduce compatibility risk.
- `seed_academic_data` is idempotent and safe to run multiple times.
- Swagger now includes clearer system-level documentation and endpoint tags for the main modules.

## Notes for Phase 3.6

- `apps.ai_gateway` is now the intended single integration point for future external AI calls.
- While `AI_SERVICE_ENABLED=false`, all AI gateway services return useful mock responses.
- `study_plans` and `quizzes` now route `generation_type="ai"` through the centralized gateway layer.
- The external AI service itself is still out of scope and not implemented here.
- No prompt playground or free-form prompt endpoint is exposed in this phase.

## Testing

Common system and stabilization tests:

```powershell
python manage.py test apps.common.tests
```

Study plans tests:

```powershell
python manage.py test apps.study_plans.tests
```

Full project tests:

```powershell
python manage.py test
```

Quizzes tests:

```powershell
python manage.py test apps.quizzes.tests
```

Phase 2 and Phase 3 regression tests:

```powershell
python manage.py test apps.study_plans.tests apps.quizzes.tests
```

Phase 3.5 regression suite:

```powershell
python manage.py test apps.common.tests apps.study_plans.tests apps.quizzes.tests
```

AI gateway tests:

```powershell
python manage.py test apps.ai_gateway.tests
```

## MVP Smoke Test Checklist

Run these in order after migrations and seed data:

1. `python manage.py seed_academic_data`
2. Register a user
3. Login and get an access token
4. Call `GET /api/users/me/`
5. Setup `StudentProfile`
6. Call `GET /api/education-stages/`
7. Call `GET /api/subjects/`
8. Add a subject to the user
9. Create a study plan
10. Call `GET /api/study-plans/today/`
11. Complete one study task
12. Create a quiz
13. Start a quiz attempt
14. Submit the attempt
15. Call `GET /api/quiz-attempts/{id}/result/`
16. Call `GET /api/health/`
17. Call `GET /api/meta/`
18. Call `GET /api/schema/`
19. Call `GET /api/docs/`

Phase 3.6 smoke additions:

20. Login as a user and call `GET /api/ai-gateway/status/`
21. Call `GET /api/ai-gateway/health/`
22. Create `StudyPlan` with `generation_type="ai"` in mock mode
23. Create `Quiz` with `generation_type="ai"` in mock mode

## Phase 4 Notes

- Files, storage, and background processing are still intentionally out of scope.
- `health` and `meta` endpoints are in place to support deployment checks and frontend coordination.
- The response helper and exception layer are prepared for broader adoption in future endpoints.
- Future AI-enabled apps should call `apps.ai_gateway` instead of integrating with external AI services directly.
- `short_answer` grading can later move to a reviewed or AI-assisted flow.
- `QuestionBankItem` can later be promoted into a richer reusable question bank.
- Quiz progress logs are ready for future analytics and recommendation services.
