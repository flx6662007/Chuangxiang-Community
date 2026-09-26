"""游客只读赛事接口，读取已维护的数据，不在页面请求中抓取或调用 AI。"""

from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Competition, CompetitionSource, CompetitionTaxonomy
from .serializers import CompetitionDetailSerializer, CompetitionListSerializer, TaxonomySerializer


class CompetitionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50

    def get_page_size(self, request):
        raw = request.query_params.get(self.page_size_query_param)
        if raw is None:
            return self.page_size
        try:
            size = int(raw)
        except (ValueError, TypeError):
            raise ValidationError({'page_size': '每页数量须为正整数。'}) from None
        if size < 1:
            raise ValidationError({'page_size': '每页数量须为正整数。'})
        return min(size, self.max_page_size)


class PublicCompetitionMixin:
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get_queryset(self):
        return Competition.objects.filter(
            publication_status=Competition.PublicationStatus.PUBLISHED,
        ).select_related('category').prefetch_related(
            'tags',
            Prefetch('sources', queryset=CompetitionSource.objects.filter(
                last_verified_at__isnull=False,
            ), to_attr='public_sources'),
        ).order_by('-published_at', '-id')


class CompetitionListView(PublicCompetitionMixin, ListAPIView):
    serializer_class = CompetitionListSerializer
    pagination_class = CompetitionPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', '').strip()
        category = self.request.query_params.get('category', '').strip()
        if len(search) > 200 or len(category) > 64:
            raise ValidationError({'detail': '搜索内容最多 200 字符，分类编码最多 64 字符。'})
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(summary__icontains=search) | Q(organizer__icontains=search),
            )
        if category:
            queryset = queryset.filter(category__code=category)
        recruitment_open = self.request.query_params.get('recruitment_open')
        if recruitment_open is not None:
            if recruitment_open not in ('true', 'false', '1', '0'):
                raise ValidationError({'recruitment_open': '请使用 true 或 false。'})
            eligible = Q(recruitment_enabled=True, recruitment_deadline__gt=timezone.now(),
                         participation_type__in=['team', 'both'])
            queryset = queryset.filter(eligible) if recruitment_open in ('true', '1') else queryset.exclude(eligible)
        return queryset


class CompetitionDetailView(PublicCompetitionMixin, RetrieveAPIView):
    serializer_class = CompetitionDetailSerializer


class CompetitionCategoriesView(ListAPIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    serializer_class = TaxonomySerializer
    pagination_class = None
    queryset = CompetitionTaxonomy.objects.filter(kind='category', is_active=True)


class CompetitionOptionsView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        rows = list(CompetitionTaxonomy.objects.filter(is_active=True))
        return Response({
            'categories': TaxonomySerializer([x for x in rows if x.kind == 'category'], many=True).data,
            'tags': TaxonomySerializer([x for x in rows if x.kind == 'tag'], many=True).data,
            'levels': [{'code': code, 'name': label} for code, label in Competition.Level.choices],
        })
