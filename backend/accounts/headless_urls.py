"""只开放本轮所需的浏览器认证入口；不开放自行换绑邮箱或 APP token。"""
from allauth.account.internal.flows.email_verification_by_code import EmailVerificationProcess
from allauth.account.internal.flows.password_reset_by_code import PasswordResetVerificationProcess
from allauth.account.internal.userkit import filter_users_by_email
from allauth.headless.account import views
from allauth.headless.account.inputs import RequestPasswordResetInput, SignupInput
from allauth.account.adapter import get_adapter
from allauth.headless.base.response import ConflictResponse, ForbiddenResponse
from allauth.headless.constants import Client
from django.http import HttpResponseNotAllowed
from django.urls import include, path
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import User
from .adapters import ensure_email_record


class SchoolSignupInput(SignupInput):
    def clean(self):
        data = super().clean()
        if data.get('password') and data.get('email'):
            try:
                get_adapter().clean_password(data['password'], user=User(email=data['email']))
            except ValidationError as exc:
                self.add_error('password', exc)
        return data

    @transaction.atomic
    def save(self, request):
        # User 与 allauth EmailAddress 同时落库；后半失败时不留下半个账号。
        return super().save(request)


class SchoolSignupView(views.SignupView):
    input_class = {'POST': SchoolSignupInput}


class PasswordAccountResetInput(RequestPasswordResetInput):
    def clean_email(self):
        email = get_adapter().clean_email(self.cleaned_data['email'].lower())
        # 当前没有 SSO：不可用密码代表非交互账号，不能借找回密码启用登录。
        self.users = [user for user in filter_users_by_email(
            email, is_active=True, prefer_verified=True, for_login=True
        ) if user.has_usable_password()]
        # 无账号与不可重置账号均走 allauth 的空用户流程，不暴露账号类型。
        return email


class PasswordAccountResetRequestView(views.RequestPasswordResetView):
    input_class = PasswordAccountResetInput


class PasswordAccountResetView(views.ResetPasswordView):
    def handle(self, request, *args, **kwargs):
        process = PasswordResetVerificationProcess.resume(request)
        if process and process.user and (
            not process.user.is_active or not process.user.has_usable_password()
        ):
            # 发码后被禁用的账号不能用旧验证码恢复密码或间接核验邮箱。
            process.abort()
            return ConflictResponse(request)
        return super().handle(request, *args, **kwargs)


class PasswordAccountChangeView(views.ChangePasswordView):
    def handle(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.has_usable_password():
            return ForbiddenResponse(request)
        return super().handle(request, *args, **kwargs)


class CurrentEmailView(views.ManageEmailView):
    def dispatch(self, request, *args, **kwargs):
        if request.method not in ('GET', 'PUT'):
            return HttpResponseNotAllowed(['GET', 'PUT'])
        if request.method == 'PUT' and request.user.is_authenticated:
            # Django Admin 登录不走 allauth 的 post_login；发码前补齐初始账号。
            ensure_email_record(request.user)
        return super().dispatch(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        address = self.input.cleaned_data['email']
        if (not request.user.is_authenticated or address.user_id != request.user.pk
                or address.email != request.user.email or not address.primary):
            return ForbiddenResponse(request)
        if address.verified:
            return ConflictResponse(request)
        process = EmailVerificationProcess.resume(request)
        if process and process.user == request.user and process.email == address.email:
            self.input.process = process
        return super().put(request, *args, **kwargs)


class CurrentVerifyEmailView(views.VerifyEmailView):
    def handle(self, request, *args, **kwargs):
        process = EmailVerificationProcess.resume(request)
        if not request.user.is_authenticated:
            return ForbiddenResponse(request)
        if process and (process.user != request.user or process.email != request.user.email
                or not process.email_address.primary or process.email_address.verified):
            process.abort()
            return ConflictResponse(request)
        return super().handle(request, *args, **kwargs)


def browser_view(cls):
    return cls.as_api_view(client=Client.BROWSER)


# 复用 allauth 的命名空间供其内部反向解析；不挂载不在本轮范围内的入口。
account_patterns = [
    path('auth/session', browser_view(views.SessionView), name='current_session'),
    path('auth/signup', browser_view(SchoolSignupView), name='signup'),
    path('auth/login', browser_view(views.LoginView), name='login'),
    path('auth/email/verify', browser_view(CurrentVerifyEmailView), name='verify_email'),
    path('account/email', browser_view(CurrentEmailView), name='manage_email'),
    path('auth/password/request', browser_view(PasswordAccountResetRequestView), name='request_password_reset'),
    path('auth/password/reset', browser_view(PasswordAccountResetView), name='reset_password'),
    path('account/password/change', browser_view(PasswordAccountChangeView), name='change_password'),
    path('auth/reauthenticate', browser_view(views.ReauthenticateView), name='reauthenticate'),
]
app_name = 'headless'
urlpatterns = [path('browser/v1/', include(([
    path('', include((account_patterns, 'headless'), namespace='account')),
], 'headless'), namespace='browser'))]
