from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ai_platform.models import AIProvider, AITaskType, ModelDeployment


class Command(BaseCommand):
    help = 'Create/update model deployment records used by the Baraq model router.'

    def handle(self, *args, **options):
        tasks = [choice for choice, _ in AITaskType.choices]
        definitions = [
            {
                'name': 'openai-default',
                'provider': AIProvider.OPENAI,
                'model_name': settings.AI_OPENAI_MODEL,
                'priority': 10,
            },
            {
                'name': 'gemini-default',
                'provider': AIProvider.GEMINI,
                'model_name': settings.AI_GEMINI_MODEL,
                'priority': 20,
            },
            {
                'name': 'deepseek-default',
                'provider': AIProvider.DEEPSEEK,
                'model_name': settings.AI_DEEPSEEK_MODEL,
                'priority': 30,
            },
        ]
        if getattr(settings, 'AI_LOCAL_BASE_URL', '') and getattr(settings, 'AI_LOCAL_MODEL', ''):
            definitions.append(
                {
                    'name': 'local-default',
                    'provider': AIProvider.LOCAL,
                    'model_name': settings.AI_LOCAL_MODEL,
                    'priority': 40,
                }
            )

        for item in definitions:
            deployment, created = ModelDeployment.objects.update_or_create(
                name=item['name'],
                defaults={
                    'provider': item['provider'],
                    'model_name': item['model_name'],
                    'supported_tasks': tasks,
                    'capabilities': {'structured_json': True},
                    'priority': item['priority'],
                    'is_active': True,
                },
            )
            verb = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(f'{verb} {deployment}'))

        self.stdout.write(
            self.style.WARNING(
                'Token prices are intentionally not hard-coded. Enter current per-million-token '
                'prices in Django Admin before enabling cost reports.'
            )
        )
