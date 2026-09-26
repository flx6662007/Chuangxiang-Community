"""将随仓库导入的虚构样例退出公共展示，保留历史与关联关系。"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from competitions.models import Competition, CompetitionTaxonomy
from competitions.services import require_editor, withdraw_competition
from ingestion.models import SourceConfig
from teams.models import RecruitmentOption


class Command(BaseCommand):
    help = '下架带固定种子编码及【虚构样例】标记的赛事，停用其选项和来源；不删除数据。'

    def add_arguments(self, parser):
        parser.add_argument('--actor-id', type=int, required=True)

    def handle(self, *args, **options):
        actor = get_user_model().objects.filter(pk=options['actor_id']).first()
        if actor is None:
            raise CommandError('管理员不存在。')
        require_editor(actor)
        prefix = Q(code__startswith='demo-r1-') | Q(code__startswith='demo-r2-')
        count = 0
        for event in Competition.objects.filter(prefix, title__startswith='【虚构样例】', publication_status='published').order_by('pk'):
            withdraw_competition(event.pk, actor=actor, reason='已接入真实官网赛事，虚构开发样例退出公开展示。')
            count += 1
        for model in (CompetitionTaxonomy, RecruitmentOption, SourceConfig):
            model.objects.filter(prefix, name__startswith='【虚构样例】', is_active=True).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f'已下架 {count} 条虚构赛事并停用对应选项/来源；历史关系保留。'))
