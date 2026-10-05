from django.urls import path
from .public_views import PublicEditorialView, PublicNewsletterView

app_name = 'public_editorial'
urlpatterns = [
    path('research/', PublicEditorialView.as_view(), name='research'),
    path('newsletters/', PublicNewsletterView.as_view(), name='newsletters'),
]
