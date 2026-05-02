# Frontend API Contract Summary

## Auth
- Type: Bearer JWT
- Header: `Authorization: Bearer <access_token>`
- Login: `POST /api/auth/login/`
- Refresh: `POST /api/auth/refresh/`

## Main Flows
- Auth: register -> login -> store access/refresh -> call `/api/users/me/` and `/api/students/profile/`.
- Onboarding: load `/api/education-stages/` and `/api/subjects/`, then call `/api/students/setup-profile/` and `/api/users/subjects/`.
- Study plans: use `/api/study-plans/`, `/api/study-plans/today/`, `/api/study-plans/week/`, and study task status endpoints.
- Quizzes: create/list -> start -> save answers -> submit -> show result/corrections.
- AI gateway: authenticated status checks from `/api/ai-gateway/status/` and `/api/ai-gateway/health/`.

## Endpoint Groups
- System: 2 endpoints
- Auth: 3 endpoints
- Users: 2 endpoints
- Students: 3 endpoints
- Subjects: 5 endpoints
- Study Plans: 9 endpoints
- Study Tasks: 6 endpoints
- Quizzes: 7 endpoints
- Quiz Attempts: 6 endpoints
- Question Bank: 2 endpoints
- AI Gateway: 2 endpoints
- API Docs: 2 endpoints

## Notes
- All API paths use a trailing slash.
- Default protected endpoints use Bearer JWT authentication.
- Most business endpoints return raw serializer data or standard DRF pagination, not an envelope.
- System and AI Gateway endpoints use the common success/data envelope from apps.common.responses.
- Most DRF validation/auth/not-found errors are wrapped by the custom exception handler into success=false/message/errors/code.
- Some manually returned errors bypass the exception handler, such as /api/study-plans/week/ with invalid start_date.
- Paginated endpoints support page and page_size. Default page size is 20 and maximum page_size is 100.
- Subjects list defaults to is_active=true unless an explicit boolean-like query value is provided.
- Quiz detail and in-progress attempt responses never expose choice is_correct before submission.
- There is no seed API endpoint. Use python manage.py seed_academic_data when the local environment has no stages or subjects.
- AI gateway mode is mock unless AI_SERVICE_ENABLED=true in backend environment.
