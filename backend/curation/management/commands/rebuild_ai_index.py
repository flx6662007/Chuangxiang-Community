"""Build the local index only from currently student-visible documents."""

from django.core.management.base import BaseCommand, CommandError
from ai_services.competition_knowledge import rebuild_index
from information_library.semantic import SemanticError


class Command(BaseCommand):
    help = '从新版公开知识正文重建 BGE 索引，供聊天与赛事匹配共用。'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='NPZ 索引路径；默认读取 COMPETITION_SEMANTIC_INDEX')

    def handle(self, *args, **options):
        try:
            count = rebuild_index(path=options.get('output'))
        except (SemanticError, OSError) as error:
            raise CommandError(str(error)) from None
        self.stdout.write(f'Indexed {count} approved chunks.')
