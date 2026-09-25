"""发布、申请服务复用的账号门槛，不替代赛事和队伍对象权限。"""
from allauth.account.models import EmailAddress
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.permissions import BasePermission

from .models import UserRestriction
from .validators import validate_school_email


def school_email_verified(user):
    if not user.is_authenticated or not user.is_active:
        return False
    try:
        validate_school_email(user.email)
    except ValidationError:
        return False
    return EmailAddress.objects.filter(user=user, email=user.email, primary=True, verified=True).exists()


def account_eligibility(user):
    reasons = []
    if not user.is_authenticated:
        return {'eligible': False, 'reasons': ['login_required'], 'restriction_ends_at': None}
    if not user.is_active:
        reasons.append('account_disabled')
    if not school_email_verified(user):
        reasons.append('email_unverified')
    now = timezone.now()
    restriction = UserRestriction.objects.filter(user=user, revoked_at__isnull=True,
        starts_at__lte=now, expires_at__gt=now).order_by('-expires_at').first()
    if restriction:
        reasons.append('account_restricted')
    if not user.has_contact_details:
        reasons.append('contact_required')
    return {'eligible': not reasons, 'reasons': reasons,
            'restriction_ends_at': restriction.expires_at if restriction else None}


class CanStartRecruitmentAction(BasePermission):
    message = '请先完成学校邮箱验证、联系方式及账号状态检查。'

    def has_permission(self, request, view):
        return account_eligibility(request.user)['eligible']
