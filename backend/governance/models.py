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
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from .validation import validate_model

class AdminAction(DomainModel):
    """管理员统一操作的必要记录，不建立举报、申诉或工单流程。"""
    immutable_fields = '*'
    action = models.CharField('操作类型', max_length=32, choices=[('publish', 'publish'), ('edit', 'edit'), ('verify', 'verify'), ('withdraw', 'withdraw'), ('restore', 'restore'), ('restrict', 'restrict'), ('revoke_restriction', 'revoke_restriction'), ('disable_account', 'disable_account'), ('enable_account', 'enable_account')])
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='用户目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    competition = models.ForeignKey('competitions.Competition', verbose_name='赛事目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    research = models.ForeignKey('research.ResearchOpportunity', verbose_name='科研目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    resource = models.ForeignKey('resources.Resource', verbose_name='资源目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    newsletter = models.ForeignKey('newsletters.Newsletter', verbose_name='快讯目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    recruitment = models.ForeignKey('teams.Recruitment', verbose_name='招募卡目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    restriction = models.ForeignKey('accounts.UserRestriction', verbose_name='关联限制记录', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='管理员', on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField('处理时间', default=timezone.now)
    reason = models.CharField('必要理由', max_length=500, default='', blank=True)
    changes = models.JSONField('必要前后状态', default=dict, blank=True)
    reverses = models.OneToOneField('governance.AdminAction', verbose_name='被撤销的操作', on_delete=models.PROTECT, related_name='+', null=True, blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'AdminAction'
        constraints = [
            models.CheckConstraint(condition=Q(target_user__isnull=False, competition__isnull=True, research__isnull=True, resource__isnull=True, newsletter__isnull=True, recruitment__isnull=True) | Q(target_user__isnull=True, competition__isnull=False, research__isnull=True, resource__isnull=True, newsletter__isnull=True, recruitment__isnull=True) | Q(target_user__isnull=True, competition__isnull=True, research__isnull=False, resource__isnull=True, newsletter__isnull=True, recruitment__isnull=True) | Q(target_user__isnull=True, competition__isnull=True, research__isnull=True, resource__isnull=False, newsletter__isnull=True, recruitment__isnull=True) | Q(target_user__isnull=True, competition__isnull=True, research__isnull=True, resource__isnull=True, newsletter__isnull=False, recruitment__isnull=True) | Q(target_user__isnull=True, competition__isnull=True, research__isnull=True, resource__isnull=True, newsletter__isnull=True, recruitment__isnull=False), name='adminaction_one_target'),
            models.CheckConstraint(condition=Q(reverses__isnull=True) | ~Q(reverses=F('id')), name='adminaction_no_self'),
            models.CheckConstraint(condition=~Q(action__in=['withdraw','restore','restrict','revoke_restriction','disable_account','enable_account']) | Q(reason__regex=r'\S'), name='adminaction_reason'),
            models.CheckConstraint(condition=Q(action__in=['publish', 'edit', 'verify', 'withdraw', 'restore', 'restrict', 'revoke_restriction', 'disable_account', 'enable_account']), name='g02_action_enum'),
            models.CheckConstraint(condition=Q(action__regex=r'\S'), name='g02_action_nonblank'),
        ]
        indexes = [
            models.Index(fields=['created_at'], name='g02_idx_1'),
            models.Index(fields=['target_user', 'created_at'], name='g02_idx_2'),
            models.Index(fields=['recruitment', 'created_at'], name='g02_idx_3'),
        ]
