"""Build resource/research BGE index from the current public database state."""

import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ai_services.unified import public_secondary_records
from ai_services.unified_index import build_index, save_index
from information_library.semantic import SemanticError


class Command(BaseCommand):
    help = '重建资源与科研公开资料的本地 BGE 索引。'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='默认读取 UNIFIED_SEMANTIC_INDEX')

    def handle(self, *args, **options):
        destination = options['output'] or os.getenv('UNIFIED_SEMANTIC_INDEX')
        if not destination:
            raise CommandError('请设置 UNIFIED_SEMANTIC_INDEX 或传入 --output。')
        try:
            index = build_index(public_secondary_records())
            path = Path(destination)
            temporary = path.with_name(path.name + '.building')
            try:
                save_index(index, temporary)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        except (SemanticError, OSError) as error:
            raise CommandError(str(error)) from None
        self.stdout.write(f"Indexed {len(index['metadata']['chunks'])} public chunks.")
