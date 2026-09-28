from django.core.management.base import BaseCommand

from competition_catalog.models import CatalogEntry, OfficialSite
from competition_catalog.registry import bind_official_competition, initialize_catalog
from ingestion.models import ProcessingResult


class Command(BaseCommand):
    help = '登记已确认的学校目录与官网；保留既有配置，不创建账号或授予权限。'

    def handle(self, *args, **options):
        created = initialize_catalog()
        bound = 0
        for result in ProcessingResult.objects.filter(status='accepted', competition__isnull=False).select_related('competition', 'source_version__source'):
            if result.source_version_id and bind_official_competition(result.competition, result.source_version.source.adapter_key):
                bound += 1
        self.stdout.write(f'新建目录 {created} 项；目录总数 {CatalogEntry.objects.count()}；官网入口 {OfficialSite.objects.count()}；已检查正式赛事关联 {bound} 次。')
