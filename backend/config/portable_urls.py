"""保留现有 API、allauth 与管理入口，为 Vue history 路由提供本机回退。"""

from django.urls import path, re_path

from .portable import frontend, portable_health, static_file
from .urls import urlpatterns as application_patterns

urlpatterns = [
    path('api/portable/health/', portable_health, name='portable-health'),
    *(pattern for pattern in application_patterns if str(pattern.pattern)),
    re_path(r'^static/(?P<path>.+)$', static_file),
    re_path(r'^(?P<path>.*)$', frontend),
]
