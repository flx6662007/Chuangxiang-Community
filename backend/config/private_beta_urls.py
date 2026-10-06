"""内测只挂载现有 API 与前端页面；后台和 allauth HTML 路由不公开。"""

from django.urls import path, re_path

from .private_beta import frontend, private_beta_status
from .urls import urlpatterns as application_patterns

urlpatterns = [
    path('api/v1/private-beta/', private_beta_status, name='private-beta-status'),
    *(pattern for pattern in application_patterns if str(pattern.pattern).startswith('api/')),
    re_path(r'^(?P<path>.*)$', frontend),
]
