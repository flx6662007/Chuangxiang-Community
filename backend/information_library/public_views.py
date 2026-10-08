"""科研和快讯的访客只读接口。"""
from django.conf import settings
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.http import Http404

from common.api import CompetitionPagination
from .public_selectors import newsletter_cards, research_cards, search_cards
from research.presentation import has_recruitment_opportunity


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
        all_rows = self.cards()
        rows = search_cards(all_rows, query)
        if type(self) is PublicEditorialView:
            recruitment = request.query_params.get('recruitment', '')
            if recruitment not in ('', '0', '1'):
                raise ValidationError({'recruitment': '招募筛选值须为 0 或 1。'})
            if recruitment == '1':
                rows = [row for row in rows if has_recruitment_opportunity(row)]
        paginator = CompetitionPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        response = paginator.get_paginated_response(page)
        if type(self) is PublicEditorialView:
            response.data['lastVerifiedOn'] = max((r['verifiedOn'] for r in all_rows if r['verifiedOn']), default='')
            response.data['statistics'] = {
                'laboratories': len(all_rows),
                'recruitmentDetails': sum(bool(r.get('details', {}).get('recruitment')) for r in all_rows),
                'recruitmentSources': sum(bool(r.get('details', {}).get('hasRecruitmentSource')) for r in all_rows),
            }
        return response


class PublicNewsletterView(PublicEditorialView):
    cards = staticmethod(newsletter_cards)


class PublicResearchDetailView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request, pk):
        for card in research_cards():
            if card['id'] == f'db-{pk}':
                return Response(card)
        raise Http404
