"""Build the local index only from currently student-visible documents."""

from django.core.management.base import BaseCommand, CommandError
from ai_services.knowledge import EmbeddingUnavailable, rebuild_index


class Command(BaseCommand):
    help = 'Rebuild approved AI knowledge vectors in the current database.'

    def handle(self, *args, **options):
        try:
            count = rebuild_index()
        except EmbeddingUnavailable as error:
            raise CommandError(str(error)) from None
        self.stdout.write(f'Indexed {count} approved chunks.')
