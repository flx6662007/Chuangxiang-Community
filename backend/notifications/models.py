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

class BusinessEvent(DomainModel):
    """业务动作及条件变更的不可变事件，保存必要确认历史并可靠生成站内消息。"""
    immutable_fields = '*'
    event_key = models.UUIDField('幂等事件标识', default=uuid.uuid4, unique=True)
    kind = models.CharField('事件类型', max_length=48, choices=[('recruitment_edited', 'recruitment_edited'), ('recruitment_closed', 'recruitment_closed'), ('application_submitted', 'application_submitted'), ('contact_opened', 'contact_opened'), ('application_confirmed', 'application_confirmed'), ('confirmation_revoked', 'confirmation_revoked'), ('application_continued', 'application_continued'), ('application_withdrawn', 'application_withdrawn'), ('application_rejected', 'application_rejected'), ('application_ended', 'application_ended'), ('member_joined', 'member_joined'), ('departure_requested', 'departure_requested'), ('departure_responded', 'departure_responded'), ('departure_withdrawn', 'departure_withdrawn'), ('departure_completed', 'departure_completed'), ('dissolution_requested', 'dissolution_requested'), ('dissolution_responded', 'dissolution_responded'), ('dissolution_withdrawn', 'dissolution_withdrawn'), ('dissolution_rejected', 'dissolution_rejected'), ('dissolution_completed', 'dissolution_completed'), ('admin_action', 'admin_action')])
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='动作用户', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    occurred_at = models.DateTimeField('事件时间', default=timezone.now)
    recruitment = models.ForeignKey('teams.Recruitment', verbose_name='卡片目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    application = models.ForeignKey('teams.Application', verbose_name='申请目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    departure_request = models.ForeignKey('teams.DepartureRequest', verbose_name='退出/移除目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    dissolution_request = models.ForeignKey('teams.DissolutionRequest', verbose_name='解散目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    admin_action = models.ForeignKey('governance.AdminAction', verbose_name='管理操作目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    payload = models.JSONField('必要事件数据', default=dict, blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'BusinessEvent'
        constraints = [
            models.CheckConstraint(condition=Q(recruitment__isnull=False, application__isnull=True, departure_request__isnull=True, dissolution_request__isnull=True, admin_action__isnull=True) | Q(recruitment__isnull=True, application__isnull=False, departure_request__isnull=True, dissolution_request__isnull=True, admin_action__isnull=True) | Q(recruitment__isnull=True, application__isnull=True, departure_request__isnull=False, dissolution_request__isnull=True, admin_action__isnull=True) | Q(recruitment__isnull=True, application__isnull=True, departure_request__isnull=True, dissolution_request__isnull=False, admin_action__isnull=True) | Q(recruitment__isnull=True, application__isnull=True, departure_request__isnull=True, dissolution_request__isnull=True, admin_action__isnull=False), name='businessevent_one_target'),
            models.CheckConstraint(condition=Q(kind__in=['recruitment_edited', 'recruitment_closed', 'application_submitted', 'contact_opened', 'application_confirmed', 'confirmation_revoked', 'application_continued', 'application_withdrawn', 'application_rejected', 'application_ended', 'member_joined', 'departure_requested', 'departure_responded', 'departure_withdrawn', 'departure_completed', 'dissolution_requested', 'dissolution_responded', 'dissolution_withdrawn', 'dissolution_rejected', 'dissolution_completed', 'admin_action']), name='m01_kind_enum'),
            models.CheckConstraint(condition=Q(kind__regex=r'\S'), name='m01_kind_nonblank'),
        ]
        indexes = [
            models.Index(fields=['application', 'occurred_at'], name='m01_idx_2'),
            models.Index(fields=['recruitment', 'occurred_at'], name='m01_idx_3'),
        ]


class Notification(DomainModel):
    """一个业务事件发给一名接收人的站内消息。"""
    immutable_fields = ('event_id', 'recipient_id', 'title', 'body', 'created_at')
    event = models.ForeignKey('notifications.BusinessEvent', verbose_name='业务事件', on_delete=models.PROTECT, related_name='+')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='接收用户', on_delete=models.PROTECT, related_name='+')
    title = models.CharField('通知标题', max_length=200)
    body = models.CharField('轻量内容', max_length=1500)
    created_at = models.DateTimeField('创建时间', default=timezone.now)
    read_at = models.DateTimeField('首次已读时间', null=True, blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'Notification'
        constraints = [
            models.UniqueConstraint(fields=['event', 'recipient'], name='notification_once'),
            models.CheckConstraint(condition=Q(read_at__isnull=True) | Q(read_at__gte=F('created_at')), name='notification_read_time'),
            models.CheckConstraint(condition=Q(body__regex=r'\S'), name='m02_body_nonblank'),
        ]
        indexes = [
            models.Index(fields=['recipient', 'read_at', 'created_at'], name='m02_idx_1'),
        ]
