from django.urls import path

from .views import CompetitionDetailView, CompetitionListView

app_name = 'competitions'

urlpatterns = [
    path('', CompetitionListView.as_view(), name='list'),
    path('<int:pk>/', CompetitionDetailView.as_view(), name='detail'),
]
