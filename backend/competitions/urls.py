from django.urls import path

from .views import CompetitionDetailView, CompetitionListView, CompetitionCategoriesView, CompetitionOptionsView

app_name = 'competitions'

urlpatterns = [
    path('', CompetitionListView.as_view(), name='list'),
    path('categories/', CompetitionCategoriesView.as_view(), name='categories'),
    path('options/', CompetitionOptionsView.as_view(), name='options'),
    path('<int:pk>/', CompetitionDetailView.as_view(), name='detail'),
]
