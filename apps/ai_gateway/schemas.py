from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class BaseAISchema:
    def to_dict(self):
        return asdict(self)


@dataclass(slots=True)
class GenerateStudyPlanRequest(BaseAISchema):
    student_level: str
    subject: str
    days: int
    daily_minutes: int
    difficulty_level: str
    goal: str
    language: str = 'ar'


@dataclass(slots=True)
class GenerateStudyPlanResponse(BaseAISchema):
    plan_title: str
    tasks: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class GenerateQuizRequest(BaseAISchema):
    subject: str
    topic: str
    difficulty_level: str
    questions_count: int
    question_types: list[str] = field(default_factory=list)
    language: str = 'ar'


@dataclass(slots=True)
class GenerateQuizResponse(BaseAISchema):
    questions: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class SummarizeTextRequest(BaseAISchema):
    text: str
    summary_type: str
    language: str = 'ar'


@dataclass(slots=True)
class SummarizeTextResponse(BaseAISchema):
    summary: str
    key_points: list[str] = field(default_factory=list)
    flashcards: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class TranscribeAudioRequest(BaseAISchema):
    file_url: str
    language: str = 'ar'


@dataclass(slots=True)
class TranscribeAudioResponse(BaseAISchema):
    text: str
    duration_seconds: int | None = None
    segments: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class GenerateRecommendationsRequest(BaseAISchema):
    student_profile: dict[str, Any]
    performance_data: dict[str, Any]
    language: str = 'ar'


@dataclass(slots=True)
class GenerateRecommendationsResponse(BaseAISchema):
    recommendations: list[str] = field(default_factory=list)
