"""公开聊天入口；只返回白名单字段和固定错误文案。"""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.exceptions import APIException, Throttled
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from .chat import chat
from .exceptions import AIInputError, AIServiceError


class ChatThrottle(SimpleRateThrottle):
    scope = 'ai_chat'
    rate = '10/min'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


ERRORS = {
    'ai_configuration_error': (503, 'AI 服务尚未配置完成，请联系管理员。'),
    'ai_authentication_error': (503, 'AI 服务认证失败，请联系管理员检查配置。'),
    'ai_insufficient_balance': (503, 'AI 服务余额不足，请联系管理员。'),
    'ai_input_error': (400, '消息格式或长度不符合要求，请缩短内容后重试。'),
    'ai_timeout': (504, 'AI 回复超时，请稍后重试。'),
    'ai_connection_error': (503, '暂时无法连接 AI 服务，请稍后重试。'),
    'ai_rate_limit': (429, 'AI 服务请求过于频繁，请稍后重试。'),
    'ai_upstream_error': (502, 'AI 服务暂时异常，请稍后重试。'),
    'ai_response_error': (502, 'AI 未返回完整有效的回答，请缩短问题后重试。'),
}


@method_decorator(csrf_protect, name='dispatch')
class ChatView(APIView):
    # 首页游客也可使用；所有 POST（包括游客）仍须通过 CSRF 校验。
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ChatThrottle]
    parser_classes = [JSONParser]
    renderer_classes = [JSONRenderer]
    http_method_names = ['post', 'options']

    def post(self, request):
        try:
            if not isinstance(request.data, dict) or set(request.data) != {'messages'}:
                raise AIInputError()
            result = chat(request.data['messages'], details=True)
            # Test doubles and legacy internal callers may still return the V1 message object.
            return Response(result if 'message' in result else {'message': result})
        except AIServiceError as error:
            status, detail = ERRORS.get(error.code, (502, 'AI 服务暂时无法完成处理。'))
            return Response({'code': error.code, 'detail': detail}, status=status)

    def handle_exception(self, exc):
        # 不透传上游响应、异常文本、请求头或 DEBUG traceback，也不记录聊天内容。
        if isinstance(exc, Throttled):
            response = Response({'code': 'ai_rate_limit', 'detail': '发送太频繁，请稍后重试。'}, status=429)
            response['Retry-After'] = str(max(1, int(exc.wait or 60)))
            return response
        if isinstance(exc, APIException):
            detail = '请求格式不正确，请刷新页面后重试。'
            if exc.status_code == 405:
                detail = '此接口只接受 POST 请求。'
            return Response({'code': 'ai_invalid_request', 'detail': detail}, status=exc.status_code)
        return Response({'code': 'ai_unavailable', 'detail': 'AI 服务暂时不可用，请稍后重试。'}, status=503)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response
