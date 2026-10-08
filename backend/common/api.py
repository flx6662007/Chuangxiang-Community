"""跨业务 API 输入、分页与异常响应；不定义业务权限。"""
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView

from .errors import BusinessError


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields) if isinstance(data, dict) else set()
        if unknown:
            raise serializers.ValidationError({'unknown_fields': sorted(unknown)})
        return super().to_internal_value(data)


class CompetitionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50

    def get_page_size(self, request):
        raw = request.query_params.get(self.page_size_query_param)
        if raw is None:
            return self.page_size
        try:
            size = int(raw)
        except (ValueError, TypeError):
            raise ValidationError({'page_size': '每页数量须为正整数。'}) from None
        if size < 1:
            raise ValidationError({'page_size': '每页数量须为正整数。'})
        return min(size, self.max_page_size)


class BusinessView(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, ObjectDoesNotExist):
            exc = BusinessError('not_found', '对象不存在或不可访问。', 404)
        elif isinstance(exc, DjangoValidationError):
            exc = BusinessError('invalid_fields', '字段不符合业务规则。', 400,
                                getattr(exc, 'message_dict', None) or {'non_field_errors': exc.messages})
        elif isinstance(exc, ValidationError):
            exc = BusinessError('invalid_fields', '请检查提交字段。', 400, exc.detail)
        elif isinstance(exc, IntegrityError):
            exc = BusinessError('conflict', '状态已改变或记录已存在，请刷新后重试。')
        return super().handle_exception(exc)

    def read_input(self, cls):
        serializer = cls(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def page(self, objects, output):
        paginator = CompetitionPagination()
        page = paginator.paginate_queryset(objects, self.request, view=self)
        return paginator.get_paginated_response([output(obj, self.request.user) for obj in page])
