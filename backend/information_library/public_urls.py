from django.urls import path
from .public_views import PublicEditorialView, PublicNewsletterView, PublicResearchDetailView

app_name = 'public_editorial'
urlpatterns = [
    path('research/', PublicEditorialView.as_view(), name='research'),
    path('research/<int:pk>/', PublicResearchDetailView.as_view(), name='research-detail'),
    path('newsletters/', PublicNewsletterView.as_view(), name='newsletters'),
]
