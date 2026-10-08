"""只读知识文档 API，与管理后台编辑和导入流程分离。"""
from rest_framework.generics import ListAPIView, RetrieveAPIView
from common.api import CompetitionPagination
from .api import LibraryReadMixin
from .selectors import filtered_documents, visible_documents
from .serializers import KnowledgeDocumentSerializer


class KnowledgeDocumentListView(LibraryReadMixin, ListAPIView):
    serializer_class = KnowledgeDocumentSerializer
    pagination_class = CompetitionPagination

    def get_queryset(self):
        return filtered_documents(self.request.query_params, self.preview)


class KnowledgeDocumentDetailView(LibraryReadMixin, RetrieveAPIView):
    serializer_class = KnowledgeDocumentSerializer
    lookup_field = 'code'

    def get_queryset(self):
        return visible_documents(self.preview)

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'detail': True}
