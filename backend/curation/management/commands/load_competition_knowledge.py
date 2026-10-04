import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from curation.knowledge_loader import load_competition_knowledge


class Command(BaseCommand):
    help = '批次导入并启用新版赛事知识；默认预演，--apply 提交全部三包和审核记录。'

    def add_arguments(self, parser):
        parser.add_argument('--actor-id', required=True, type=int, help='执行导入和批次审核的管理员编号')
        parser.add_argument('--reason', required=True, help='本次知识版本的审核依据')
        parser.add_argument('--directory', type=Path, help='包含三个 import-*.json 的目录')
        parser.add_argument('--report', type=Path, help='保存 UTF-8 JSON 执行报告')
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--preview', action='store_true', help='预演完整导入与审核流程')
        mode.add_argument('--apply', action='store_true', help='提交导入并启用知识检索')

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options['actor_id'])
            result = load_competition_knowledge(actor=actor, reason=options['reason'],
                apply=options['apply'], directory=options['directory'])
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        output = json.dumps(result, ensure_ascii=False, sort_keys=True)
        if options['report']:
            options['report'].parent.mkdir(parents=True, exist_ok=True)
            options['report'].write_text(output + '\n', encoding='utf-8')
        self.stdout.write(output)
