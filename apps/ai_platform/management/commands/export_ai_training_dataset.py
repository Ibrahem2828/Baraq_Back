import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.ai_platform.models import TrainingDatasetCandidate


class Command(BaseCommand):
    help = 'Export only human-approved, anonymized AI examples as versioned JSONL.'

    def add_arguments(self, parser):
        parser.add_argument('--version', required=True)
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        version = options['version'].strip()
        output_path = Path(options['output']).expanduser().resolve()
        queryset = TrainingDatasetCandidate.objects.filter(
            dataset_version=version,
            human_review_status=TrainingDatasetCandidate.ReviewStatus.APPROVED,
            approved_for_training=True,
            pii_status='filtered',
            anonymization_status='completed',
        ).select_related('output__request', 'feedback')
        if not queryset.exists():
            raise CommandError(f'No approved candidates found for dataset version {version}.')

        output_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with output_path.open('w', encoding='utf-8') as handle:
            for candidate in queryset.iterator():
                request = candidate.output.request
                record = {
                    'dataset_version': version,
                    'task_type': request.task_type,
                    'character': request.character,
                    'input': candidate.anonymized_input,
                    'expected_output': candidate.expected_output,
                    'provenance': {
                        'candidate_id': candidate.id,
                        'prompt_version_id': request.prompt_version_id,
                        'provider': request.selected_provider,
                        'model': request.selected_model,
                        'feedback_rating': getattr(candidate.feedback, 'rating', None),
                    },
                }
                handle.write(json.dumps(record, ensure_ascii=False) + '\n')
                count += 1
        self.stdout.write(self.style.SUCCESS(f'Exported {count} examples to {output_path}'))
        self.stdout.write(
            self.style.WARNING(
                'Do not launch fine-tuning automatically. Run offline evaluation, approval, '
                'shadow testing, and a canary release first.'
            )
        )
