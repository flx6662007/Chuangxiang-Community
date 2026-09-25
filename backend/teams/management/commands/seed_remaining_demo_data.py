"""整批、可重复执行的第二轮虚构数据导入。"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ingestion.models import SourceConfig
from teams.demo_data import DemoBuilder, MARKER, PREFIX, SOURCE_CODE
from teams.models import Team


class Command(BaseCommand):
    help='仅 DEBUG：导入第二轮全模块虚构数据；重复执行整体保留，不重置期限或改写历史。'
    requires_migrations_checks=True

    @transaction.atomic
    def handle(self,*args,**options):
        if not settings.DEBUG:
            raise CommandError('仅限 DEBUG=1 的本地开发库。')
        source=SourceConfig.objects.filter(code=SOURCE_CODE).first()
        if source:
            users=get_user_model().objects.filter(email__in=[f'cxdemo-r2-{n:03d}@tongji.edu.cn' for n in range(1,13)])
            valid_users=users.count()==12 and all(not u.is_active and not u.is_staff and not u.is_superuser and not u.has_usable_password() for u in users)
            if not source.name.startswith(MARKER) or source.is_active or not valid_users or Team.objects.filter(code__in=[PREFIX+f'team-{n}' for n in range(1,4)]).count()!=3:
                raise CommandError('样例标识冲突或根记录不完整；保留已有数据，不自动覆盖或补造。')
            self.stdout.write('SKIPPED: 第二轮样例已存在；未新增、未覆盖、未重置有效期。')
            return
        DemoBuilder(timezone.now()).build()
        self.stdout.write(self.style.SUCCESS('CREATED: 第二轮虚构样例已整批导入；无邮件、抓取或 AI 外部调用。'))
