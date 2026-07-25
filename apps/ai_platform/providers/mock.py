from __future__ import annotations

from typing import Any

from .base import BaseAIProvider, ProviderResult


class MockProvider(BaseAIProvider):
    provider_name = 'mock'

    @property
    def configured(self) -> bool:
        return True

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        temperature: float = 0.2,
        max_output_tokens: int = 4000,
    ) -> ProviderResult:
        # Intentionally deterministic. It exists for development/tests only.
        properties = output_schema.get('properties') or {}
        if 'questions' in properties:
            data = {
                'quiz_title': 'اختبار تجريبي من فاحص',
                'questions': [
                    {
                        'question_type': 'mcq',
                        'question': 'ما الفكرة الأساسية في المصدر؟',
                        'choices': ['الفكرة الأولى', 'الفكرة الثانية', 'الفكرة الثالثة', 'الفكرة الرابعة'],
                        'correct_answer_index': 0,
                        'explanation': 'هذه نتيجة تجريبية ويجب استبدالها بمزود فعلي.',
                        'difficulty': 'medium',
                        'topic': 'المصدر',
                        'source_reference': {'source_id': None, 'chunk_index': 0, 'page_number': None},
                    }
                ],
            }
        elif 'plan_days' in properties:
            data = {
                'plan_title': 'خطة تجريبية من خُطى',
                'summary': 'خطة تطويرية لاختبار التكامل فقط.',
                'plan_days': [
                    {
                        'date': '2026-01-01',
                        'tasks': [
                            {
                                'subject': 'المادة',
                                'topic': 'مراجعة المصدر',
                                'task_type': 'review',
                                'estimated_minutes': 30,
                                'priority': 'medium',
                                'reason': 'بدء المراجعة بالمفاهيم الأساسية.',
                            }
                        ],
                    }
                ],
            }
        elif 'recommendations' in properties:
            data = {
                'overall_score': 0,
                'strengths': [],
                'weaknesses': ['لا توجد بيانات كافية في وضع المحاكاة.'],
                'recommendations': ['أكمل اختباراً حقيقياً ليتمكن رشيد من التحليل.'],
                'next_best_action': 'حل اختبار قصير في المادة.',
                'evidence': [],
            }
        elif 'short_summary' in properties:
            data = {
                'short_summary': 'ملخص تجريبي.',
                'detailed_summary': 'هذه نتيجة تجريبية لاختبار التكامل.',
                'key_points': ['نقطة تجريبية'],
                'important_terms': [],
                'review_questions': [],
                'covered_topics': [],
                'source_references': [],
            }
        else:
            data = {'message': 'Mock AI result'}
        return ProviderResult(data=data, model_name='mock-v1')
