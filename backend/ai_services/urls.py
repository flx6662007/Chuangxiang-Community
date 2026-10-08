from django.urls import path
from .views import ChatView, StreamChatView, AssistantSearchView, AssistantStatusView
from .guide_views import CompetitionGuideView

urlpatterns = [
    path("guide/", CompetitionGuideView.as_view(), name="competition-guide"),
    path("chat/", ChatView.as_view(), name="ai-chat"),
    path("chat/stream/", StreamChatView.as_view(), name="ai-chat-stream"),
    path("search/", AssistantSearchView.as_view(), name="assistant-search"),
    path("status/", AssistantStatusView.as_view(), name="assistant-status"),
]
