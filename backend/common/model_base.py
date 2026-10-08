"""与具体业务无关的字段归一化和时区校验。"""
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class CleanFieldsModel(models.Model):
    """字段校验前统一去除文本首尾空白；不隐式替代写入事务。"""

    class Meta:
        abstract = True

    def clean_fields(self, exclude=None):
        for field in self._meta.fields:
            value = getattr(self, field.attname)
            if field.name not in (exclude or ()) and isinstance(value, str):
                setattr(self, field.attname, value.strip())
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        errors = {}
        for field in self._meta.fields:
            value = getattr(self, field.attname)
            if isinstance(field, models.DateTimeField) and isinstance(value, datetime):
                if timezone.is_naive(value):
                    errors[field.name] = '请提供带时区的时间。'
        if errors:
            raise ValidationError(errors)
