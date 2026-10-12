"""Local single-origin preview: existing APIs plus built Vue routes."""

from django.urls import re_path

from .portable import frontend, static_file
from .urls import urlpatterns as application_patterns

urlpatterns = [
    *(pattern for pattern in application_patterns if str(pattern.pattern)),
    re_path(r'^static/(?P<path>.+)$', static_file),
    re_path(r'^(?P<path>.*)$', frontend),
]
