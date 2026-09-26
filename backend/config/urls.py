"""网址入口：将请求路径分发给相应处理代码。"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from .views import HealthView

urlpatterns = [
    path('', RedirectView.as_view(url='/api/v1/health/', permanent=False)),
    path('api/v1/health/', HealthView.as_view(), name='health'),
    path('api/v1/competitions/', include('competitions.urls')),
    path('api/v1/accounts/', include('accounts.urls')),
    path('api/v1/', include('teams.urls')),
    path('api/v1/notifications/', include('notifications.urls')),
    path('api/auth/', include('accounts.headless_urls')),
    path('accounts/', include('allauth.urls')),
    # 用户模型和数据库迁移完成后，管理后台才能登录使用。
    path('admin/', admin.site.urls),
]
