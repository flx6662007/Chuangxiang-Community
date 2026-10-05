from django.urls import path
from .api_views import CatalogDetailView, CatalogListView

urlpatterns = [
    path('', CatalogListView.as_view(), name='competition-catalog-list'),
    path('<slug:code>/', CatalogDetailView.as_view(), name='competition-catalog-detail'),
]
