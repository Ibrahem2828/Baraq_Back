# Student Sources MVP

Student Sources let an authenticated student upload study material and then use
one Baraq character with that source.

This MVP stores files safely, reads plain text files, exposes capabilities for
the frontend, and records character interactions. It does not run real AI, OCR,
document parsing, summarization, or audio transcription yet.

## Endpoints

- `GET /api/student-sources/`
- `POST /api/student-sources/`
- `GET /api/student-sources/{id}/`
- `PATCH /api/student-sources/{id}/`
- `DELETE /api/student-sources/{id}/`
- `POST /api/student-sources/{id}/process/`
- `GET /api/student-sources/{id}/capabilities/`
- `POST /api/student-sources/{id}/use-with-character/`
- `POST /api/student-sources/{id}/use-with-khota/`
- `POST /api/student-sources/{id}/use-with-fahes/`
- `POST /api/student-sources/{id}/use-with-rasheed/`
- `POST /api/student-sources/{id}/use-with-kholasa/`
- `POST /api/student-sources/{id}/use-with-sada/`

All endpoints require `Authorization: Bearer <access_token>`. A student can only
see and act on sources owned by that same user.

## Upload

`POST /api/student-sources/` uses `multipart/form-data`.

Fields:

- `title`: required.
- `description`: optional.
- `subject`: optional subject id.
- `file`: required.

## Supported Files

Allowed extensions: `pdf`, `txt`, `jpg`, `jpeg`, `png`, `webp`, `doc`, `docx`,
`ppt`, `pptx`, `mp3`, `m4a`, `wav`.

Blocked examples: `exe`, `sh`, `bat`, `cmd`, `js`, `html`, `php`, `py`, `jar`,
`zip`, `rar`, `7z`, `sql`, `env`.

Default maximum size: `25MB`, configured by `STUDENT_SOURCE_MAX_UPLOAD_MB`.

## Processing

- TXT: read synchronously and store `extracted_text`; status becomes `ready`.
- PDF: saved only; advanced parsing later.
- Images: saved only; OCR later.
- Word/PowerPoint: saved only; document parsing later.
- Audio: saved only; transcription through صدى later.

## Capabilities

`GET /api/student-sources/{id}/capabilities/` returns availability for خُطى,
فاحص, رشيد, خلاصة, and صدى.

خُطى creates a basic study plan and four tasks when the source has a subject.
فاحص creates a quiz shell and simple short-answer questions when TXT content is
available. رشيد returns study advice. خلاصة and صدى return unavailable messages.

## Storage Notes

Files are stored under:

```text
student_sources/<user_id>/<year>/<month>/<uuid>.<ext>
```

Development media serving is enabled only when `DEBUG=True`.

Production must use persistent media storage. Docker Compose mounts `media_data`
at `/app/media`; Coolify, Nginx, or object storage should serve `/media/`.
