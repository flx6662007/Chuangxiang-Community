"""学校邮箱策略：保留 allauth 的密码、会话和验证码实现。"""
import smtplib

from allauth.account.adapter import DefaultAccountAdapter
from allauth.headless.adapter import DefaultHeadlessAdapter

from .managers import UserManager
from .validators import validate_school_email


def ensure_email_record(user):
    """仅为完全缺失邮箱记录的旧用户补未验证主邮箱。"""
    from allauth.account.models import EmailAddress
    from django.db import transaction
    from .models import User
    with transaction.atomic():
        current = User.objects.select_for_update().get(pk=user.pk)
        if not EmailAddress.objects.filter(user=current).exists():
            EmailAddress.objects.create(user=current, email=current.email, primary=True, verified=False)


class EmailDeliveryError(Exception):
    """只返回稳定错误，不泄露 SMTP 凭据或原始响应。"""


class SchoolAccountAdapter(DefaultAccountAdapter):
    def clean_email(self, email):
        email = UserManager.normalize_email(email)
        validate_school_email(email)
        return email

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        self.clean_password(form.cleaned_data.get('password') or form.cleaned_data.get('password1'), user=user)
        if commit:
            user.save()
        return user

    def get_login_stages(self):
        # 允许未验证用户登录；验证码在账号页主动发送，业务写权限另行检查。
        return [stage for stage in super().get_login_stages()
                if stage != 'allauth.account.stages.EmailVerificationStage']

    def post_login(self, request, user, **kwargs):
        ensure_email_record(user)
        return super().post_login(request, user, **kwargs)

    def send_mail(self, template_prefix, email, context):
        try:
            return super().send_mail(template_prefix, email, context)
        except (smtplib.SMTPException, OSError):
            raise EmailDeliveryError('邮件服务暂不可用，请稍后重试。') from None


class SchoolHeadlessAdapter(DefaultHeadlessAdapter):
    def serialize_user(self, user):
        # 此载荷亦可能出现在部分认证响应中；联系方式仅供本人资料接口读取。
        return {'id': user.pk, 'display': user.public_code, 'public_code': user.public_code,
                'has_usable_password': user.has_usable_password()}
