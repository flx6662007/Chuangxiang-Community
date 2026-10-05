from django.urls import path
from .views import KnowledgeDocumentDetailView, KnowledgeDocumentListView

urlpatterns = [
    path('', KnowledgeDocumentListView.as_view(), name='knowledge-document-list'),
    path('<slug:code>/', KnowledgeDocumentDetailView.as_view(), name='knowledge-document-detail'),
]
