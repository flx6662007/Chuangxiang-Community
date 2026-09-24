"""网址入口：将请求路径分发给相应处理代码。"""
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

from .views import HealthView

urlpatterns = [
    path('', RedirectView.as_view(url='/api/v1/health/', permanent=False)),
    path('api/v1/health/', HealthView.as_view(), name='health'),
    # 用户模型和数据库迁移完成后，管理后台才能登录使用。
    path('admin/', admin.site.urls),
]
