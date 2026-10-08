"""Library HTTP API reads the database only; browsing never fetches external pages."""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from competition_catalog.models import CatalogEntry
from common.api import CompetitionPagination
from curation.api import LibraryReadMixin

from .models import ResourceTaxonomy
from .selectors import filter_catalog, resource_catalog_map, resource_options, visible_resources
from .serializers import ResourceSerializer, taxonomy


class ResourceListView(LibraryReadMixin, APIView):
    def get(self, request):
        preview = self.preview
        queryset = visible_resources(preview)
        fields = {'search': 200, 'category': 64, 'direction': 64, 'catalog_code': 16}
        values = {}
        for field, length in fields.items():
            value = request.query_params.get(field, '').strip()
            if len(value) > length:
                raise ValidationError({field: f'最多输入 {length} 个字符。'})
            values[field] = value
        search = values['search']
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search)
                                       | Q(provider__icontains=search))
        category, direction = values['category'], values['direction']
        if category == 'unclassified':
            queryset = queryset.filter(category__isnull=True)
        elif category:
            if not ResourceTaxonomy.objects.filter(kind='category', code=category).exists():
                raise ValidationError({'category': '资源分类不存在。'})
            queryset = queryset.filter(category__code=category, category__kind='category')
        if direction:
            if not ResourceTaxonomy.objects.filter(kind='direction', code=direction).exists():
                raise ValidationError({'direction': '资源方向不存在。'})
            queryset = queryset.filter(directions__code=direction, directions__kind='direction')
        catalog_code = values['catalog_code']
        if catalog_code:
            if not CatalogEntry.objects.filter(code=catalog_code, is_active=True).exists():
                raise ValidationError({'catalog_code': '赛事目录编号不存在。'})
            queryset = filter_catalog(queryset, catalog_code, preview)
        paginator = CompetitionPagination()
        page = paginator.paginate_queryset(queryset.distinct(), request)
        serializer = ResourceSerializer(page, many=True, context={
            'catalog_map': resource_catalog_map(page, preview),
        })
        return paginator.get_paginated_response(serializer.data)


class ResourceDetailView(LibraryReadMixin, APIView):
    def get(self, request, code):
        preview = self.preview
        resource = get_object_or_404(visible_resources(preview), code=code)
        return Response(ResourceSerializer(resource, context={
            'detail': True, 'catalog_map': resource_catalog_map([resource], preview),
        }).data)


class ResourceOptionsView(LibraryReadMixin, APIView):
    def get(self, request):
        categories, directions, unclassified = resource_options(self.preview)
        return Response({
            'categories': [taxonomy(item, 'category') for item in categories],
            'directions': [taxonomy(item, 'direction') for item in directions],
            'has_unclassified': unclassified,
        })
