"""本人资料及 CSRF 入口；认证和验证码由 allauth Headless 实现。"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .permissions import account_eligibility, school_email_verified
from .serializers import ContactSerializer


@never_cache
@require_GET
def csrf_token(request):
    return JsonResponse({'csrfToken': get_token(request)})


def csrf_failure(request, reason=''):
    return JsonResponse({'detail': '页面凭据失效，请刷新后重试。', 'code': 'csrf_failed'}, status=403)


def profile_data(user):
    return {'id': user.pk, 'public_code': user.public_code, 'email': user.email,
            'wechat_id': user.wechat_id, 'phone_number': user.phone_number,
            'contact_updated_at': user.contact_updated_at,
            'school_email_verified': school_email_verified(user),
            'has_contact_details': user.has_contact_details,
            'account_eligibility': account_eligibility(user)}


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response

    def get(self, request):
        return Response(profile_data(request.user))

    def patch(self, request):
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            serializer = ContactSerializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            for name, value in serializer.validated_data.items():
                setattr(user, name, value)
            try:
                user.save(update_fields=set(serializer.validated_data))
            except ValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from None
        return Response(profile_data(user))
