from django.urls import path

from .views import ResourceDetailView, ResourceListView, ResourceOptionsView

urlpatterns = [
    path('', ResourceListView.as_view(), name='resource-list'),
    path('options/', ResourceOptionsView.as_view(), name='resource-options'),
    path('<slug:code>/', ResourceDetailView.as_view(), name='resource-detail'),
]
