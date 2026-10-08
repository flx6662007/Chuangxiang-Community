"""游客只读赛事接口，读取已维护的数据，不在页面请求中抓取或调用 AI。"""

from django.db.models import Q
from django.utils import timezone
from rest_framework.generics import ListAPIView, RetrieveAPIView
from common.api import CompetitionPagination
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Competition, CompetitionTaxonomy
from .serializers import CompetitionDetailSerializer, CompetitionListSerializer, TaxonomySerializer
from .scope import apply_competition_scope
from .selectors import DEMO_PREFIX, public_competition_queryset
from .timeliness import TIME_STATUSES


def public_taxonomies():
    return CompetitionTaxonomy.objects.filter(is_active=True).exclude(DEMO_PREFIX, name__startswith='【虚构样例】')


class PublicCompetitionMixin:
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get_queryset(self):
        return public_competition_queryset()


class CompetitionListView(PublicCompetitionMixin, ListAPIView):
    serializer_class = CompetitionListSerializer
    pagination_class = CompetitionPagination

    def get_queryset(self):
        queryset = apply_competition_scope(super().get_queryset())
        time_status = self.request.query_params.get('time_status', 'current')
        if time_status not in TIME_STATUSES:
            raise ValidationError({'time_status': '请使用 current、expired 或 all。'})
        if time_status == 'current':
            queryset = queryset.exclude(_deadline_status='closed')
        elif time_status == 'expired':
            queryset = queryset.filter(_deadline_status='closed')
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
            from .recruitment_policy import open_query
            eligible = open_query(timezone.now())
            queryset = queryset.filter(eligible) if recruitment_open in ('true', '1') else queryset.exclude(eligible)
        return queryset


class CompetitionDetailView(PublicCompetitionMixin, RetrieveAPIView):
    serializer_class = CompetitionDetailSerializer


class CompetitionCategoriesView(ListAPIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    serializer_class = TaxonomySerializer
    pagination_class = None
    queryset = public_taxonomies().filter(kind='category')


class CompetitionOptionsView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        rows = list(public_taxonomies())
        return Response({
            'categories': TaxonomySerializer([x for x in rows if x.kind == 'category'], many=True).data,
            'tags': TaxonomySerializer([x for x in rows if x.kind == 'tag'], many=True).data,
            'levels': [{'code': code, 'name': label} for code, label in Competition.Level.choices],
        })
