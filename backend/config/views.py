"""项目基础接口；账号、赛事等业务接口写在各自模块中。"""

from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """确认后端能够响应 HTTP 请求；不检查数据库或业务功能。"""

    # 无需用户表：即使请求携带旧登录 Cookie，也不执行用户认证。
    authentication_classes = []
    permission_classes = [AllowAny]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        return Response({'status': 'ok', 'service': 'chuangxiang-backend'})
