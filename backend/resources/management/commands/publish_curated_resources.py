"""明确指定资料包中的学习资源发布；不处理赛事和知识正文。"""
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from curation.models import ImportedObject
from resources.models import Resource, ResourceTaxonomy
from resources.services import publish_resource


class Command(BaseCommand):
    help = '发布指定已导入资料包的学习外链，默认只列数量；不会审核正文或开启赛事组队。'

    def add_arguments(self, parser):
        parser.add_argument('--package-id', action='append', required=True)
        parser.add_argument('--actor-id', type=int)
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        codes = ImportedObject.objects.filter(
            kind='resource', package_id__in=options['package_id'],
        ).values('code')
        resources = Resource.objects.filter(code__in=codes).order_by('code')
        if not resources.exists():
            raise CommandError('没有找到所指定资料包的已入库学习资源。')
        stats = {'total': resources.count(), 'draft': resources.filter(publication_status='draft').count(),
                 'published': resources.filter(publication_status='published').count(),
                 'mode': 'apply' if options['apply'] else 'preview'}
        if options['apply']:
            if not options['actor_id']:
                raise CommandError('--apply 需要 --actor-id。')
            actor = get_user_model().objects.get(pk=options['actor_id'])
            if not (actor.is_active and actor.is_staff and actor.has_perm('resources.change_resource')):
                raise CommandError('需要具有资源维护权限的有效管理员。')
            category, _ = ResourceTaxonomy.objects.get_or_create(
                code='competition-learning', defaults={'kind': 'category', 'name': '赛事学习资料'},
            )
            category.full_clean()
            for resource in resources:
                publish_resource(resource.pk, actor=actor, category=resource.category or category)
            stats['published_after'] = resources.filter(publication_status='published').count()
        self.stdout.write(json.dumps(stats, ensure_ascii=False))
