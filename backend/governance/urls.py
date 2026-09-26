from django.urls import path
from . import views

urlpatterns = [
    path('options/', views.OptionsView.as_view()),
    path('reports/', views.ReportListView.as_view()),
    path('reports/<int:pk>/', views.ReportDetailView.as_view()),
    path('appeals/', views.AppealListView.as_view()),
    path('appeals/<int:pk>/', views.AppealDetailView.as_view()),
    path('appeal-targets/', views.AppealTargetsView.as_view()),
]
