"""将明确选定的人工资料包直接公开，不伪造独立事实核验。"""
import json
from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from competitions.models import Competition, CompetitionTaxonomy
from competitions.services import publish_competition_direct
from curation.models import ImportedObject, KnowledgeDocument
from curation.services import publish_document


class Command(BaseCommand):
    help = '直接发布指定已导入资料包的届次和知识正文；默认只预览数量，不改日期或开启组队。'

    def add_arguments(self, parser):
        parser.add_argument('--package-id', action='append', required=True)
        parser.add_argument('--actor-id', type=int)
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        stamps = ImportedObject.objects.filter(package_id__in=options['package_id'])
        present = set(stamps.values_list('package_id', flat=True))
        if set(options['package_id']) - present:
            raise CommandError('部分指定资料包尚未导入，请核对 package-id。')
        competitions = Competition.objects.filter(code__in=stamps.filter(kind='competition').values('code')).order_by('code')
        documents = KnowledgeDocument.objects.filter(code__in=stamps.filter(kind='document').values('code')).order_by('code')
        result = {'mode': 'apply' if options['apply'] else 'preview',
                  'competitions': competitions.count(), 'documents': documents.count()}
        if options['apply']:
            if not options['actor_id']:
                raise CommandError('--apply 需要 --actor-id。')
            actor = get_user_model().objects.get(pk=options['actor_id'])
            if not (actor.is_active and actor.is_staff and actor.has_perms([
                'competitions.change_competition', 'curation.change_knowledgedocument', 'curation.add_documentreview',
            ])):
                raise CommandError('需要有效维护身份以及赛事、知识文档发布权限。')
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_advisory_xact_lock(%s)', [2026131255])
            category, _ = CompetitionTaxonomy.objects.get_or_create(
                code='catalog-competition', defaults={'kind': 'category', 'name': '目录赛事'},
            )
            category.full_clean()
            counts = Counter()
            reason = '按项目负责人决定直接公开已整理资料；本操作不代表逐项事实核验。'
            for item in competitions:
                status = item.publication_status
                publish_competition_direct(item.pk, actor=actor, category=item.category or category, reason=reason)
                counts['competitions_unchanged' if status == 'published' else 'competitions_published'] += 1
            for item in documents:
                status = item.review_status
                publish_document(item.code, actor=actor, reason=reason)
                counts['documents_unchanged' if status in ('published', 'approved') else 'documents_published'] += 1
            result.update(counts)
        self.stdout.write(json.dumps(result, ensure_ascii=False))
