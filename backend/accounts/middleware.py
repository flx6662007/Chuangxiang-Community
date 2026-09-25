from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from .adapters import EmailDeliveryError


class AccountAPIErrorMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if not request.path.startswith('/api/auth/'):
            return None
        if isinstance(exception, EmailDeliveryError):
            return JsonResponse({'status': 503, 'errors': [{'code': 'email_unavailable',
                'message': '邮件发送失败，请稍后重试；账号验证状态没有改变。'}]}, status=503)
        if isinstance(exception, IntegrityError):
            return JsonResponse({'status': 409, 'errors': [{'code': 'account_conflict',
                'message': '账号信息冲突，请尝试登录或重新提交。'}]}, status=409)
        if isinstance(exception, ValidationError):
            return JsonResponse({'status': 400, 'errors': [{'code': 'account_invalid',
                'message': '账号信息未通过校验，请检查输入或尝试登录。'}]}, status=400)
        return None
