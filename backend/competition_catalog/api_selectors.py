"""目录是赛事身份，Competition 是具体届次；两者不相互冒充。"""
from collections import defaultdict
from django.db.models import Count, Q
from rest_framework.exceptions import ValidationError
from competitions.models import Competition
from curation.models import DocumentLink
from curation.selectors import visible_documents
from resources.selectors import visible_resources, resource_association_revisions
from .models import CatalogBinding, CatalogEntry


def visible_editions(preview=False):
    statuses = ('published', 'draft') if preview else ('published',)
    return Competition.objects.filter(publication_status__in=statuses).exclude(
        code__startswith='demo-').exclude(title__contains='【虚构样例】')


def catalog_entries(params):
    queryset = CatalogEntry.objects.filter(is_active=True).order_by('code')
    search = params.get('search', '').strip()
    grade = params.get('grade', '').strip()
    if len(search) > 200 or len(grade) > 8:
        raise ValidationError('搜索最多 200 字符，等级最多 8 字符。')
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
    if grade:
        queryset = queryset.filter(grade=grade)
    return queryset


def catalog_counts(entries, preview=False):
    """按当前页批量查询，避免每张目录卡分别访问数据库。"""
    ids = [entry.pk for entry in entries]
    result = {pk: {'competition_count': 0, 'resource_count': 0, 'document_count': 0} for pk in ids}
    if not ids:
        return result
    for row in CatalogBinding.objects.filter(
        entry_id__in=ids, competition_id__in=visible_editions(preview).values('pk'),
    ).values('entry_id').annotate(total=Count('competition_id', distinct=True)):
        result[row['entry_id']]['competition_count'] = row['total']
    revisions = visible_documents(preview).values('current_revision_id')
    catalog_links = list(DocumentLink.objects.filter(
        catalog_id__in=ids, revision_id__in=revisions,
    ).values_list('catalog_id', 'revision_id'))
    for entry_id, revision_id in catalog_links:
        result[entry_id]['document_count'] += 1
    # 公开资源的目录归属可独立使用；不因此公开关联的待审核知识正文。
    catalogs_by_revision = defaultdict(set)
    for entry_id, revision_id in DocumentLink.objects.filter(
        catalog_id__in=ids, revision_id__in=resource_association_revisions(),
    ).values_list('catalog_id', 'revision_id'):
        catalogs_by_revision[revision_id].add(entry_id)
    resources_by_catalog = defaultdict(set)
    for revision_id, resource_id in DocumentLink.objects.filter(
        revision_id__in=catalogs_by_revision,
        resource_id__in=visible_resources(preview).values('pk'),
    ).values_list('revision_id', 'resource_id'):
        for entry_id in catalogs_by_revision[revision_id]:
            resources_by_catalog[entry_id].add(resource_id)
    for entry_id, resources in resources_by_catalog.items():
        result[entry_id]['resource_count'] = len(resources)
    return result
