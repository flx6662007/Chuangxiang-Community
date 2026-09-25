from django.urls import path
from .views import MeView, csrf_token

app_name = 'accounts'
urlpatterns = [path('csrf/', csrf_token, name='csrf'), path('me/', MeView.as_view(), name='me')]
