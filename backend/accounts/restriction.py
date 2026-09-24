"""本轮确认模型；写入须 full_clean，并在事务服务中执行跨表联动。"""
from datetime import timedelta
import uuid

from django.conf import settings
from django.core.validators import MaxLengthValidator, MinValueValidator, URLValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from common.models import DomainModel
from common.codes import new_code

class UserRestriction(DomainModel):
    """沿用已确认用户字段表，新增实现而不改变规则。"""
    immutable_fields = ('user_id', 'reason', 'starts_at', 'expires_at', 'created_by_id')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='被限制用户', on_delete=models.PROTECT, related_name='+')
    reason = models.CharField('处理理由', max_length=500)
    starts_at = models.DateTimeField('限制开始', default=timezone.now)
    expires_at = models.DateTimeField('原定到期')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='处理管理员', on_delete=models.PROTECT, related_name='+')
    revoked_at = models.DateTimeField('提前解除时间', null=True, blank=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='提前解除管理员', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    revoke_reason = models.CharField('解除理由', max_length=500, default='', blank=True)

    @property
    def is_effective(self):
        return self.revoked_at is None and self.starts_at <= timezone.now() < self.expires_at

    class Meta:
        verbose_name = 'UserRestriction'
        constraints = [
            models.CheckConstraint(condition=Q(expires_at=F('starts_at') + timedelta(hours=24)), name='userrestriction_24_hours'),
            models.CheckConstraint(condition=Q(revoked_at__isnull=True, revoked_by__isnull=True, revoke_reason='') | Q(revoked_at__isnull=False, revoked_by__isnull=False, revoked_at__gte=F('starts_at'), revoked_at__lt=F('expires_at'), revoke_reason__regex=r'\S'), name='userrestriction_revocation'),
            models.CheckConstraint(condition=Q(reason__regex=r'\S'), name='g01_reason_nonblank'),
        ]
        indexes = [
            models.Index(fields=['user', 'expires_at'], name='g01_idx_1'),
        ]
