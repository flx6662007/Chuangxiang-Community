from django.urls import path
from . import views

urlpatterns = [
    path('recruitments/options/', views.RecruitmentOptionsView.as_view()),
    path('recruitments/preview/', views.RecruitmentPreviewView.as_view()),
    path('recruitments/', views.RecruitmentListView.as_view()),
    path('recruitments/<int:pk>/', views.RecruitmentDetailView.as_view()),
    path('recruitments/<int:pk>/close/', views.RecruitmentCloseView.as_view()),
    path('recruitments/<int:pk>/applications/', views.ApplicationCreateView.as_view()),
    path('applications/', views.ApplicationListView.as_view()),
    path('applications/<int:pk>/', views.ApplicationDetailView.as_view()),
    path('applications/<int:pk>/contact/', views.ApplicationContactView.as_view()),
    path('applications/<int:pk>/<slug:action>/', views.ApplicationActionView.as_view()),
    path('teams/mine/', views.TeamListView.as_view()),
    path('teams/<int:pk>/', views.TeamDetailView.as_view()),
    path('memberships/<int:pk>/departure-requests/', views.DepartureCreateView.as_view()),
    path('departure-requests/<int:pk>/respond/', views.DepartureActionView.as_view(), {'action': 'respond'}),
    path('departure-requests/<int:pk>/withdraw/', views.DepartureActionView.as_view(), {'action': 'withdraw'}),
    path('teams/<int:pk>/dissolution-requests/', views.DissolutionCreateView.as_view()),
    path('dissolution-requests/<int:pk>/respond/', views.DissolutionActionView.as_view(), {'action': 'respond'}),
    path('dissolution-requests/<int:pk>/withdraw/', views.DissolutionActionView.as_view(), {'action': 'withdraw'}),
]
