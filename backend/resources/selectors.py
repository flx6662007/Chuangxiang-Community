"""Resource visibility and catalog associations are independent of knowledge-body approval."""

from collections import defaultdict

from curation.models import DocumentLink, KnowledgeDocument

from .models import Resource, ResourceTaxonomy


def visible_resources(preview=False):
    statuses = ('published', 'draft') if preview else ('published',)
    return Resource.objects.filter(
        publication_status__in=statuses, availability='available',
    ).exclude(code__startswith='demo-').exclude(title__contains='【虚构样例】').select_related(
        'category',
    ).prefetch_related('tags', 'directions').order_by('-updated_at', 'code')


def resource_association_revisions():
    """Use current, non-withdrawn links only; this grants no access to document bodies."""
    return KnowledgeDocument.objects.filter(
        review_status__in=('draft', 'published', 'approved'), current_revision__isnull=False,
    ).values_list('current_revision_id', flat=True)


def filter_catalog(queryset, catalog_code, preview=False):
    revisions = DocumentLink.objects.filter(
        revision_id__in=resource_association_revisions(),
        catalog__code=catalog_code, catalog__is_active=True,
    ).values_list('revision_id', flat=True)
    linked_resources = DocumentLink.objects.filter(
        revision_id__in=revisions, resource_id__in=visible_resources(preview).values('pk'),
    ).values_list('resource_id', flat=True)
    return queryset.filter(pk__in=linked_resources)


def resource_catalog_map(resources, preview=False):
    """Build page-wide associations in two queries, without leaking old revision links."""
    identifiers = [resource.pk for resource in resources]
    result = defaultdict(list)
    if not identifiers:
        return result
    links = list(DocumentLink.objects.filter(
        revision_id__in=resource_association_revisions(), resource_id__in=identifiers,
    ).filter(resource_id__in=visible_resources(preview).values('pk')).values_list('revision_id', 'resource_id'))
    resources_by_revision = defaultdict(set)
    for revision_id, resource_id in links:
        resources_by_revision[revision_id].add(resource_id)
    entries = DocumentLink.objects.filter(
        revision_id__in=resources_by_revision, catalog__is_active=True,
    ).values_list('revision_id', 'catalog__code', 'catalog__name').order_by('catalog__code')
    seen = defaultdict(set)
    for revision_id, code, name in entries:
        for resource_id in resources_by_revision[revision_id]:
            if code not in seen[resource_id]:
                result[resource_id].append({'code': code, 'name': name})
                seen[resource_id].add(code)
    return result


def resource_options(preview=False):
    """Expose actual controlled terms in visible resources, rather than mock categories."""
    resources = visible_resources(preview)
    categories = ResourceTaxonomy.objects.filter(
        kind='category', pk__in=resources.values_list('category_id', flat=True),
    ).order_by('sort_order', 'code')
    directions = ResourceTaxonomy.objects.filter(
        kind='direction', pk__in=resources.values_list('directions__pk', flat=True),
    ).order_by('sort_order', 'code')
    return categories, directions, resources.filter(category__isnull=True).exists()
