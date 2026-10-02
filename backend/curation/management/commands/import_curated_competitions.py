import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from curation.package import load_package


class Command(BaseCommand):
    help = '人工资料包离线校验；默认不写库。--preview 在事务内预演并回滚；--apply 只导入已审核资料包为草稿。'

    def add_arguments(self, parser):
        parser.add_argument('package')
        parser.add_argument('--batch', type=int, choices=range(1, 6), action='append', default=[])
        parser.add_argument('--actor-id', type=int)
        parser.add_argument('--report', type=Path, help='将校验结果或失败原因保存为 UTF-8 JSON')
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--preview', action='store_true')
        mode.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            data = load_package(options['package'], options['batch'])
            result = {'mode': 'validate', 'package_id': data['package_id'],
                      'counts': {k: len(data[k]) for k in ('catalog', 'competitions', 'resources', 'documents')}}
            if options['preview'] or options['apply']:
                if not options['actor_id']:
                    raise ValueError('--preview/--apply 需要 --actor-id。')
                from curation.importer import import_package
                actor = get_user_model().objects.get(pk=options['actor_id'])
                result = {'mode': 'apply' if options['apply'] else 'preview-rolled-back',
                          'counts': import_package(data, actor=actor, apply=options['apply'])}
        except Exception as exc:
            if options['report']:
                options['report'].parent.mkdir(parents=True, exist_ok=True)
                options['report'].write_text(json.dumps({'ok': False, 'error': str(exc),
                    'batch': options['batch'], 'database_transaction': 'not-committed'}, ensure_ascii=False, indent=2), encoding='utf-8')
            raise CommandError(str(exc)) from exc
        result['ok'] = True
        result['batch'] = options['batch']
        if options['report']:
            options['report'].parent.mkdir(parents=True, exist_ok=True)
            options['report'].write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
