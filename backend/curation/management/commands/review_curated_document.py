from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from curation.services import review_document


class Command(BaseCommand):
    help = '记录指定知识文档版本的审核结果；不发布关联赛事或资源。'

    def add_arguments(self, parser):
        parser.add_argument('code')
        parser.add_argument('--revision', required=True, type=int)
        parser.add_argument('--status', required=True, choices=['approved', 'withdrawn', 'draft'])
        parser.add_argument('--reason', required=True)
        parser.add_argument('--actor-id', required=True, type=int)

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options['actor_id'])
            record = review_document(options['code'], revision=options['revision'],
                status=options['status'], reason=options['reason'], actor=actor)
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f'已记录审核 {record.pk}；版本 {record.revision.version}；状态 {record.status}。')
