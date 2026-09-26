import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from ingestion.models import SourceConfig
from ingestion.services import initialize_sources, sync_source


class Command(BaseCommand):
    help = '从启用的官方来源发现/复查真实赛事；记录原文、候选和失败，不在网页请求中运行。'

    def add_arguments(self, parser):
        parser.add_argument('--source', action='append', help='来源 code，可重复；省略时运行全部启用来源')
        parser.add_argument('--trigger', choices=('manual', 'scheduled'), default='scheduled')
        parser.add_argument('--actor-id', type=int, help='人工初始化/采集的管理员 ID，不接受用户名密码')
        parser.add_argument('--init-sources', action='store_true', help='登记两个内置官方来源；不覆盖已有配置')
        parser.add_argument('--auto-accept', action='store_true', help='按已核验规则采纳完整新记录，无害更新须未被人工修改')
        parser.add_argument('--enable-recruitment', action='store_true', help='对新收录且人数/报名日明确的赛事启用保守平台招募期限')
        parser.add_argument('--max-pages', type=int, default=20, help='每来源最多获取的文章数，1–50')

    def handle(self, *args, **options):
        actor = None
        if options['actor_id']:
            actor = get_user_model().objects.filter(pk=options['actor_id']).first()
            if actor is None:
                raise CommandError('管理员不存在。')
        if options['init_sources'] or options['trigger'] == 'manual':
            if actor is None:
                raise CommandError('初始化或手动采集必须指定 --actor-id。')
        if not 1 <= options['max_pages'] <= 50:
            raise CommandError('--max-pages 必须为 1–50。')
        try:
            if options['init_sources']:
                initialize_sources(actor=actor)
            sources = SourceConfig.objects.filter(is_active=True, content_kind='competition').order_by('id')
            if options['source']:
                sources = sources.filter(code__in=options['source'])
                if set(sources.values_list('code', flat=True)) != set(options['source']):
                    raise CommandError('指定来源不存在或已停用。')
            if not sources.exists():
                raise CommandError('没有启用来源。先由管理员运行 --init-sources --actor-id。')
            failed = 0
            for source in sources:
                try:
                    stats = sync_source(source, actor=actor, trigger=options['trigger'],
                        auto_accept=options['auto_accept'], enable_recruitment=options['enable_recruitment'],
                        max_pages=options['max_pages'])
                    self.stdout.write(json.dumps(stats, ensure_ascii=False))
                    failed += stats['failed']
                except (ValidationError, PermissionDenied) as exc:
                    self.stderr.write(f'{source.code}: {exc}')
                    failed += 1
            if failed:
                raise CommandError(f'{failed} 项来源获取/处理失败；已保留其他成功结果，详见 Admin 获取记录。')
        except (ValidationError, PermissionDenied) as exc:
            raise CommandError(str(exc)) from exc
