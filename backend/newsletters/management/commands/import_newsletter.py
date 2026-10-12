import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from newsletters.importer import DEFAULT_PACKAGE, load_package, plan_import, import_issue


class Command(BaseCommand):
    help = '预览人工快讯包；--write 保存草稿；--write --publish 明确发布。'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DEFAULT_PACKAGE))
        parser.add_argument('--write', action='store_true')
        parser.add_argument('--publish', action='store_true')
        parser.add_argument('--actor-id', type=int)

    def handle(self, *args, **options):
        try:
            if options['publish'] and not options['write']:
                raise CommandError('--publish 必须同时提供 --write。')
            data = load_package(options['file'])
            self.stdout.write(json.dumps(plan_import(data), ensure_ascii=False, indent=2))
            if not options['write']:
                self.stdout.write('仅预览：未写入数据库。')
                return
            if not options['actor_id']:
                raise CommandError('写入需要 --actor-id 指定有维护权限的管理员。')
            actor = get_user_model().objects.get(pk=options['actor_id'])
            issue, changed = import_issue(data, actor=actor, publish=options['publish'])
            self.stdout.write(f"{'已处理' if changed else '内容一致，未重复写入'}：{issue.code} / {issue.publication_status}")
        except (ValidationError, PermissionDenied, IntegrityError, ValueError, KeyError, TypeError,
                OSError, get_user_model().DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
