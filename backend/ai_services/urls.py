from django.urls import path
from .views import ChatView, AssistantSearchView, AssistantStatusView

urlpatterns = [
    path("chat/", ChatView.as_view(), name="ai-chat"),
    path("search/", AssistantSearchView.as_view(), name="assistant-search"),
    path("status/", AssistantStatusView.as_view(), name="assistant-status"),
]
