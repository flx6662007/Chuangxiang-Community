"""科研和快讯的访客只读接口。"""
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
        query = request.query_params.get('search', '').strip()
        if len(query) > 200:
            raise ValidationError({'search': '搜索内容最多 200 字。'})
        rows = search_cards(self.cards(), query)
        paginator = CompetitionPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(page)


class PublicNewsletterView(PublicEditorialView):
    cards = staticmethod(newsletter_cards)
