from django.contrib import admin
from django.urls import path

from . import views

app_name = 'information_library'

urlpatterns = [
    path('', admin.site.admin_view(views.index), name='index'),
    path('<str:kind>/<str:identifier>/', admin.site.admin_view(views.detail), name='detail'),
]
