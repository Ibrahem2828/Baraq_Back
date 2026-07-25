from __future__ import annotations

from typing import Any


def _strict_object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        'type': 'object',
        'properties': properties,
        'required': required,
        'additionalProperties': False,
    }


SOURCE_REFERENCE_SCHEMA = _strict_object(
    {
        'source_id': {'type': ['integer', 'null']},
        'chunk_index': {'type': ['integer', 'null']},
        'page_number': {'type': ['integer', 'null']},
    },
    ['source_id', 'chunk_index', 'page_number'],
)

FAHES_SCHEMA = _strict_object(
    {
        'quiz_title': {'type': 'string'},
        'questions': {
            'type': 'array',
            'minItems': 1,
            'maxItems': 50,
            'items': _strict_object(
                {
                    'question_type': {'type': 'string', 'enum': ['mcq', 'true_false']},
                    'question': {'type': 'string'},
                    'choices': {
                        'type': 'array',
                        'minItems': 2,
                        'maxItems': 4,
                        'items': {'type': 'string'},
                    },
                    'correct_answer_index': {'type': 'integer', 'minimum': 0, 'maximum': 3},
                    'explanation': {'type': 'string'},
                    'difficulty': {'type': 'string', 'enum': ['easy', 'medium', 'hard']},
                    'topic': {'type': 'string'},
                    'source_reference': SOURCE_REFERENCE_SCHEMA,
                },
                [
                    'question_type',
                    'question',
                    'choices',
                    'correct_answer_index',
                    'explanation',
                    'difficulty',
                    'topic',
                    'source_reference',
                ],
            ),
        },
    },
    ['quiz_title', 'questions'],
)

KHOTA_TASK_SCHEMA = _strict_object(
    {
        'subject': {'type': 'string'},
        'topic': {'type': 'string'},
        'task_type': {'type': 'string', 'enum': ['study', 'review', 'practice', 'quiz']},
        'estimated_minutes': {'type': 'integer', 'minimum': 5, 'maximum': 240},
        'priority': {'type': 'string', 'enum': ['low', 'medium', 'high']},
        'reason': {'type': 'string'},
    },
    ['subject', 'topic', 'task_type', 'estimated_minutes', 'priority', 'reason'],
)

KHOTA_SCHEMA = _strict_object(
    {
        'plan_title': {'type': 'string'},
        'summary': {'type': 'string'},
        'plan_days': {
            'type': 'array',
            'minItems': 1,
            'maxItems': 60,
            'items': _strict_object(
                {
                    'date': {'type': 'string', 'format': 'date'},
                    'tasks': {'type': 'array', 'items': KHOTA_TASK_SCHEMA, 'minItems': 1},
                },
                ['date', 'tasks'],
            ),
        },
    },
    ['plan_title', 'summary', 'plan_days'],
)

RASHEED_SCHEMA = _strict_object(
    {
        'overall_score': {'type': ['number', 'null'], 'minimum': 0, 'maximum': 100},
        'strengths': {'type': 'array', 'items': {'type': 'string'}},
        'weaknesses': {'type': 'array', 'items': {'type': 'string'}},
        'recommendations': {'type': 'array', 'minItems': 1, 'items': {'type': 'string'}},
        'next_best_action': {'type': 'string'},
        'evidence': {
            'type': 'array',
            'items': _strict_object(
                {'metric': {'type': 'string'}, 'value': {'type': 'string'}},
                ['metric', 'value'],
            ),
        },
    },
    ['overall_score', 'strengths', 'weaknesses', 'recommendations', 'next_best_action', 'evidence'],
)

KHOLASA_SCHEMA = _strict_object(
    {
        'short_summary': {'type': 'string'},
        'detailed_summary': {'type': 'string'},
        'key_points': {'type': 'array', 'items': {'type': 'string'}},
        'important_terms': {
            'type': 'array',
            'items': _strict_object(
                {'term': {'type': 'string'}, 'definition': {'type': 'string'}},
                ['term', 'definition'],
            ),
        },
        'review_questions': {'type': 'array', 'items': {'type': 'string'}},
        'covered_topics': {'type': 'array', 'items': {'type': 'string'}},
        'source_references': {'type': 'array', 'items': SOURCE_REFERENCE_SCHEMA},
    },
    [
        'short_summary',
        'detailed_summary',
        'key_points',
        'important_terms',
        'review_questions',
        'covered_topics',
        'source_references',
    ],
)

SADA_SCHEMA = _strict_object(
    {
        'full_transcript': {'type': 'string'},
        'segments': {
            'type': 'array',
            'items': _strict_object(
                {
                    'start': {'type': 'number', 'minimum': 0},
                    'end': {'type': 'number', 'minimum': 0},
                    'text': {'type': 'string'},
                },
                ['start', 'end', 'text'],
            ),
        },
        'detected_topics': {'type': 'array', 'items': {'type': 'string'}},
        'duration_seconds': {'type': ['number', 'null'], 'minimum': 0},
        'confidence_score': {'type': ['number', 'null'], 'minimum': 0, 'maximum': 1},
    },
    ['full_transcript', 'segments', 'detected_topics', 'duration_seconds', 'confidence_score'],
)
