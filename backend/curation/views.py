"""只读知识文档 API，与管理后台编辑和导入流程分离。"""
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from competitions.views import CompetitionPagination
from .api_permissions import library_preview
from .selectors import filtered_documents, visible_documents
from .serializers import KnowledgeDocumentSerializer


class LibraryReadMixin:
    permission_classes = (AllowAny,)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.preview = library_preview(request)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response


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
