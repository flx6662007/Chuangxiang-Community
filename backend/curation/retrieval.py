"""页面与 AI 共用的公开资料范围，包括直接发布和已核验资料。"""
from django.db.models import Exists, OuterRef, Q, F
from django.conf import settings
from competitions.models import Competition
from competitions.scope import apply_competition_scope
from .models import DocumentLink, KnowledgeDocument, ImportedObject


def student_visible_documents():
    queryset = KnowledgeDocument.objects.filter(
        review_status__in=('published', 'approved'), current_revision__isnull=False,
    ).exclude(
        Q(current_revision__links__competition__publication_status__in=['draft', 'withdrawn']) |
        Q(current_revision__links__resource__publication_status__in=['draft', 'withdrawn']) |
        Q(current_revision__links__resource__availability='unavailable') |
        Q(code__startswith='demo-') | Q(current_revision__title__contains='【虚构样例】') |
        Q(current_revision__links__competition__code__startswith='demo-') |
        Q(current_revision__links__competition__title__contains='【虚构样例】') |
        Q(current_revision__links__resource__code__startswith='demo-') |
        Q(current_revision__links__resource__title__contains='【虚构样例】')
    ).distinct()
    # Once the independent release covers a catalog, its old package documents
    # remain in maintenance history and no longer duplicate the public reading set.
    replacements = DocumentLink.objects.filter(catalog_id=OuterRef('catalog_id'),
        revision_id=F('revision__document__current_revision_id'),
        revision__document__code__startswith='final-')
    replaced_links = DocumentLink.objects.filter(revision_id=OuterRef('current_revision_id'),
        catalog__isnull=False).annotate(_replacement=Exists(replacements)).filter(_replacement=True)
    legacy_codes = ImportedObject.objects.filter(kind='document', package_id__startswith='tongji-2026-').values('code')
    queryset = queryset.annotate(_has_replacement=Exists(replaced_links)).exclude(
        code__in=legacy_codes, _has_replacement=True)
    if settings.COMPETITION_CATALOG_ONLY:
        allowed_competitions = apply_competition_scope(
            Competition.objects.filter(publication_status='published'),
        ).values('pk')
        blocked_link = DocumentLink.objects.filter(revision_id=OuterRef('current_revision_id')).filter(
            Q(catalog__is_active=False) | Q(competition__isnull=False),
        ).exclude(competition_id__in=allowed_competitions, catalog__isnull=True)
        queryset = queryset.annotate(_blocked_link=Exists(blocked_link)).filter(_blocked_link=False)
    return queryset
