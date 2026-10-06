"""科研和快讯的访客只读接口。"""
from django.conf import settings
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from competitions.views import CompetitionPagination
from .public_selectors import newsletter_cards, research_cards, search_cards


class PublicEditorialView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    cards = staticmethod(research_cards)

    def get(self, request):
        if type(self) is PublicEditorialView and not settings.PUBLIC_RESEARCH_ENABLED:
            return Response({'count':0,'next':None,'previous':None,'results':[], 'available':False})
        query = request.query_params.get('search', '').strip()
        if len(query) > 200:
            raise ValidationError({'search': '搜索内容最多 200 字。'})
        rows = search_cards(self.cards(), query)
        paginator = CompetitionPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(page)


class PublicNewsletterView(PublicEditorialView):
    cards = staticmethod(newsletter_cards)
