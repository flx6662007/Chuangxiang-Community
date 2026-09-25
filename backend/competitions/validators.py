"""赛事字段的格式与来源时区校验。"""

import re
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


validate_code = RegexValidator(
    r'\A[a-z0-9]+(?:-[a-z0-9]+)*\Z', '编码请使用小写字母、数字及分隔用短横线。'
)


def parse_source_timezone(value):
    if re.fullmatch(r'[+-]\d{2}:\d{2}', value):
        hours, minutes = map(int, value[1:].split(':'))
        if hours <= 23 and minutes <= 59:
            offset = timedelta(hours=hours, minutes=minutes)
            return timezone(offset if value[0] == '+' else -offset)
    else:
        try:
            return ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    raise ValidationError('时区需为有效 IANA 名称或 ±HH:MM 偏移。')


def validate_source_timezone(value):
    parse_source_timezone(value)
