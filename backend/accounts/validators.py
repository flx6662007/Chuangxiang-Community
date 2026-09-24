"""账号字段的基础校验；联系方式验证不等于归属认证。"""

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, validate_email


def validate_school_email(value):
    validate_email(value)
    if value.rsplit('@', 1)[-1] != 'tongji.edu.cn':
        raise ValidationError('请使用 @tongji.edu.cn 学校邮箱。', code='school_email')


validate_public_code = RegexValidator(
    r'\ACX-[A-Z0-9]{8}\Z', '系统代号必须为 CX- 加 8 位大写字母或数字。'
)
validate_wechat_id = RegexValidator(
    r'\A[A-Za-z0-9_-]+\Z', '微信号只能包含英文字母、数字、下划线和短横线。'
)
validate_phone_number = RegexValidator(
    r'\A\+?[0-9][0-9 ()-]*[0-9]\Z',
    '手机号请填写数字，可带开头的 +、空格、括号和短横线。',
)
