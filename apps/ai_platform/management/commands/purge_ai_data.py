from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.ai_platform.models import AIRequest


class Command(BaseCommand):
    help = (
        'Delete expired AI requests/outputs/feedback that are not part of an '
        'approved training dataset. Use --dry-run before destructive execution.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=int(getattr(settings, 'AI_DATA_RETENTION_DAYS', 180)),
            help='Delete eligible AI history older than this number of days.',
        )
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        days = options['days']
        if days < 1:
            raise CommandError('--days must be at least 1.')
        cutoff = timezone.now() - timedelta(days=days)
        queryset = (
            AIRequest.objects.filter(created_at__lt=cutoff)
            .exclude(output__training_candidate__approved_for_training=True)
        )
        count = queryset.count()
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: {count} AI requests are eligible before {cutoff.isoformat()}.'
                )
            )
            return
        queryset.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f'Deleted {count} expired AI requests and their dependent data.'
            )
        )
