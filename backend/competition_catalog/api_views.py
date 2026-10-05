from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from competitions.views import CompetitionPagination
from curation.views import LibraryReadMixin
from .api_selectors import catalog_counts, catalog_entries, visible_editions
from .api_serializers import CatalogSerializer, edition_summary
from .models import CatalogEntry


class CatalogListView(LibraryReadMixin, ListAPIView):
    pagination_class = CompetitionPagination

    def get(self, request):
        page = self.paginate_queryset(catalog_entries(request.query_params))
        serializer = CatalogSerializer(page, many=True, context={'counts': catalog_counts(page, self.preview)})
        return self.get_paginated_response(serializer.data)


class CatalogDetailView(LibraryReadMixin, APIView):
    def get(self, request, code):
        entry = get_object_or_404(CatalogEntry, code=code, is_active=True)
        result = CatalogSerializer(entry, context={'counts': catalog_counts([entry], self.preview)}).data
        editions = visible_editions(self.preview).filter(catalog_bindings__entry=entry).order_by('-updated_at', 'code')
        result['competitions'] = [edition_summary(item) for item in editions]
        return Response(result)
