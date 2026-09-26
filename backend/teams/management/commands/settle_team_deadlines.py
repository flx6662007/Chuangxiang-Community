from django.core.management.base import BaseCommand
from django.utils import timezone
from teams.models import Team
from teams.services import lock_competition_graph, reconcile_competition


class Command(BaseCommand):
    help = '结算招募卡到期、退出/移除及整队解散的固定 24 小时期限。'

    def handle(self, *args, **options):
        count = 0
        for competition_id in Team.objects.values_list('competition_id', flat=True).distinct():
            with lock_competition_graph(competition_id):
                reconcile_competition(competition_id, now=timezone.now())
            count += 1
        self.stdout.write(self.style.SUCCESS(f'已结算 {count} 个赛事届次的组队状态。'))
