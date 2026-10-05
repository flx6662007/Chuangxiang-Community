"""学生端知识检索统一使用此审核与关联对象可见边界。"""
from django.db.models import Exists, OuterRef, Q
from django.conf import settings
from competitions.models import Competition
from competitions.scope import apply_competition_scope
from .models import DocumentLink, KnowledgeDocument


def student_visible_documents():
    queryset = KnowledgeDocument.objects.filter(
        review_status='approved', current_revision__isnull=False,
    ).exclude(
        Q(current_revision__links__competition__publication_status__in=['draft', 'withdrawn']) |
        Q(current_revision__links__resource__publication_status__in=['draft', 'withdrawn']) |
        Q(current_revision__links__resource__availability='unavailable')
    ).distinct()
    if settings.COMPETITION_CATALOG_ONLY:
        allowed_competitions = apply_competition_scope(
            Competition.objects.filter(publication_status='published'),
        ).values('pk')
        blocked_link = DocumentLink.objects.filter(revision_id=OuterRef('current_revision_id')).filter(
            Q(catalog__is_active=False) | Q(competition__isnull=False),
        ).exclude(competition_id__in=allowed_competitions, catalog__isnull=True)
        queryset = queryset.annotate(_blocked_link=Exists(blocked_link)).filter(_blocked_link=False)
    return queryset
