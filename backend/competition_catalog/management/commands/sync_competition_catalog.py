import json

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q
from django.utils import timezone

from competition_catalog.models import OfficialSite
from competition_catalog.monitor import Session, sync_site


class Command(BaseCommand):
    help = '按学校目录持续检查已核对官网，保存通知及版本；不会把通用解析结果自动发布。'

    def add_arguments(self, parser):
        parser.add_argument('--code', action='append', help='学校目录编号，可重复')
        parser.add_argument('--limit', type=int, default=300, help='本轮最多官网入口，1—500')
        parser.add_argument('--max-pages', type=int, default=3, help='每入口本轮最多页面，1—10')
        parser.add_argument('--force', action='store_true', help='手动忽略下次检查时间，仍遵守网站robots与频率')

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 500 or not 1 <= options['max_pages'] <= 10:
            raise CommandError('limit 必须为1—500，max-pages必须为1—10。')
        sites = OfficialSite.objects.filter(enabled=True, entry__is_active=True).select_related('entry')
        if options['code']:
            sites = sites.filter(entry__code__in=options['code'])
        if not options['force']:
            sites = sites.filter(Q(next_check_at__isnull=True) | Q(next_check_at__lte=timezone.now()))
        sites = sites.order_by(F('last_checked_at').asc(nulls_first=True), 'entry__code', 'pk')[:options['limit']]
        session = Session()
        failures, count = 0, 0
        try:
            for site in sites:
                result = sync_site(site, max_pages=options['max_pages'], session=session)
                self.stdout.write(json.dumps(result, ensure_ascii=False))
                self.stdout.flush()
                count += 1
                failures += result['status'] in ('failed', 'partial')
        finally:
            session.close()
        self.stdout.write(json.dumps({'checked_sites': count, 'failed_or_partial': failures}, ensure_ascii=False))
        if failures:
            raise CommandError(f'{failures} 个入口未完全成功；其他结果已保存，后台可查失败原因。')
