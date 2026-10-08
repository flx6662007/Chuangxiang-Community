"""公开赛事读取范围与排序，供 HTTP 接口和知识检索共用。"""
from django.db.models import F, OuterRef, Prefetch, Q, Subquery

from .models import Competition, CompetitionSource
from .timeliness import annotate_timeliness


DEMO_PREFIX = Q(code__startswith='demo-r1-') | Q(code__startswith='demo-r2-')


def public_competition_queryset():
    queryset = Competition.objects.filter(
        publication_status=Competition.PublicationStatus.PUBLISHED,
    ).exclude(DEMO_PREFIX, title__startswith='【虚构样例】').select_related('category').prefetch_related(
        'tags',
        Prefetch('sources', queryset=CompetitionSource.objects.filter(
            Q(last_verified_at__isnull=False) | Q(competition__publication_method=Competition.PublicationMethod.DIRECT),
        ), to_attr='public_sources'),
    )
    return annotate_timeliness(queryset).annotate(
        _source_date=Subquery(CompetitionSource.objects.filter(
            competition_id=OuterRef('pk'), is_primary=True,
        ).values('source_published_on')[:1]),
    ).order_by('-_still_open', F('_source_date').desc(nulls_last=True), '-published_at', '-id')
