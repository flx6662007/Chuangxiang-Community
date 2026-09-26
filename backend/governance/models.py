"""本轮确认模型；写入须 full_clean，并在事务服务中执行跨表联动。"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from common.models import DomainModel
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from .validation import validate_model

class AdminAction(DomainModel):
    """管理员实际操作的不可变记录，与举报和申诉的复核结论分别保存。"""
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


class ReviewRecord(DomainModel):
    """提交正文不能改写；处理完成后结论亦不能原地改写。"""
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='提交人', on_delete=models.PROTECT, related_name='+')
    target_title = models.CharField('提交时的对象名称', max_length=240)
    description = models.CharField('具体说明', max_length=1000)
    created_at = models.DateTimeField('提交时间', default=timezone.now)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='处理人', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    reviewed_at = models.DateTimeField('处理时间', null=True, blank=True)
    feedback = models.CharField('给提交人的处理反馈', max_length=1000, default='', blank=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.status == 'pending':
            if self.reviewed_by_id or self.reviewed_at or self.feedback:
                raise ValidationError('待处理记录不能预填处理结论。')
        elif not (self.reviewed_by_id and self.reviewed_at and self.feedback.strip()):
            raise ValidationError('已处理记录须包含处理人、时间和反馈。')
        if self.reviewed_by_id and self.reviewed_by_id == self.submitted_by_id:
            raise ValidationError('不能处理本人提交的记录。')
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if old and old.status != 'pending' and any(
                getattr(old, key) != getattr(self, key)
                for key in ('status', 'reviewed_by_id', 'reviewed_at', 'feedback')
            ):
                raise ValidationError('已处理结论不能改写；不同意见应通过申诉保存。')


def review_constraints(prefix, statuses):
    return [
        models.CheckConstraint(condition=Q(status__in=statuses), name=prefix + '_status'),
        models.CheckConstraint(condition=Q(description__regex=r'\S'), name=prefix + '_description'),
        models.CheckConstraint(condition=Q(target_title__regex=r'\S'), name=prefix + '_title'),
        models.CheckConstraint(condition=Q(status='pending', reviewed_by__isnull=True, reviewed_at__isnull=True, feedback='') |
            (~Q(status='pending') & Q(reviewed_by__isnull=False, reviewed_at__isnull=False, feedback__regex=r'\S')),
            name=prefix + '_review_complete'),
        models.CheckConstraint(condition=Q(reviewed_at__isnull=True) | Q(reviewed_at__gte=F('created_at')), name=prefix + '_time'),
        models.CheckConstraint(condition=Q(reviewed_by__isnull=True) | ~Q(reviewed_by=F('submitted_by')), name=prefix + '_not_self'),
    ]


class Report(ReviewRecord):
    class Reason(models.TextChoices):
        FALSE_INFORMATION = 'false_information', '信息不实或过期'
        FRAUD = 'fraud', '涉嫌诈骗或不当收费'
        INAPPROPRIATE = 'inappropriate', '内容不当'
        OTHER = 'other', '其他问题'

    class Status(models.TextChoices):
        PENDING = 'pending', '待核实'
        CONFIRMED = 'confirmed', '问题已确认'
        DISMISSED = 'dismissed', '未确认违规'

    immutable_fields = ('submitted_by_id', 'competition_id', 'recruitment_id', 'reason', 'description', 'target_title', 'created_at')
    competition = models.ForeignKey('competitions.Competition', verbose_name='被举报赛事', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    recruitment = models.ForeignKey('teams.Recruitment', verbose_name='被举报招募', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    reason = models.CharField('问题类型', max_length=24, choices=Reason.choices)
    status = models.CharField('状态', max_length=16, choices=Status.choices, default=Status.PENDING)

    class Meta:
        verbose_name = '举报'
        verbose_name_plural = '举报'
        constraints = review_constraints('report', ['pending', 'confirmed', 'dismissed']) + [
            models.CheckConstraint(condition=Q(competition__isnull=False, recruitment__isnull=True) | Q(competition__isnull=True, recruitment__isnull=False), name='report_one_target'),
            models.CheckConstraint(condition=Q(reason__in=['false_information', 'fraud', 'inappropriate', 'other']), name='report_reason'),
            models.UniqueConstraint(fields=['submitted_by', 'competition'], condition=Q(status='pending', competition__isnull=False), name='report_pending_competition'),
            models.UniqueConstraint(fields=['submitted_by', 'recruitment'], condition=Q(status='pending', recruitment__isnull=False), name='report_pending_recruitment'),
        ]
        indexes = [models.Index(fields=['submitted_by', '-created_at'], name='report_owner_time'), models.Index(fields=['status', 'created_at'], name='report_review_queue')]


class Appeal(ReviewRecord):
    class Status(models.TextChoices):
        PENDING = 'pending', '待复核'
        UPHELD = 'upheld', '申诉成立'
        REJECTED = 'rejected', '申诉未获支持'

    immutable_fields = ('submitted_by_id', 'restriction_id', 'admin_action_id', 'report_id', 'description', 'target_title', 'created_at')
    restriction = models.ForeignKey('accounts.UserRestriction', verbose_name='被申诉限制', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    admin_action = models.ForeignKey(AdminAction, verbose_name='被申诉下架操作', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    report = models.ForeignKey(Report, verbose_name='被申诉举报结论', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    status = models.CharField('状态', max_length=16, choices=Status.choices, default=Status.PENDING)

    @property
    def original_reviewer_id(self):
        if self.restriction_id:
            return self.restriction.created_by_id
        if self.admin_action_id:
            return self.admin_action.actor_id
        if self.report_id:
            return self.report.reviewed_by_id
        return None

    def clean(self):
        super().clean()
        if self.restriction_id and self.restriction.user_id != self.submitted_by_id:
            raise ValidationError('只能申诉本人的限制记录。')
        if self.admin_action_id:
            action = self.admin_action
            if action.action != 'withdraw' or not action.recruitment_id or action.recruitment.team.recruiter_id != self.submitted_by_id:
                raise ValidationError('只能申诉本人招募的管理员下架记录。')
        if self.report_id and (self.report.submitted_by_id != self.submitted_by_id or self.report.status == 'pending'):
            raise ValidationError('只能申诉本人已处理举报的结论。')
        if self.reviewed_by_id and self.reviewed_by_id == self.original_reviewer_id:
            raise ValidationError('申诉须由原处理人之外的管理员复核。')

    class Meta:
        verbose_name = '申诉'
        verbose_name_plural = '申诉'
        constraints = review_constraints('appeal', ['pending', 'upheld', 'rejected']) + [
            models.CheckConstraint(condition=Q(restriction__isnull=False, admin_action__isnull=True, report__isnull=True) |
                Q(restriction__isnull=True, admin_action__isnull=False, report__isnull=True) |
                Q(restriction__isnull=True, admin_action__isnull=True, report__isnull=False), name='appeal_one_target'),
            models.UniqueConstraint(fields=['submitted_by', 'restriction'], condition=Q(status='pending', restriction__isnull=False), name='appeal_pending_restriction'),
            models.UniqueConstraint(fields=['submitted_by', 'admin_action'], condition=Q(status='pending', admin_action__isnull=False), name='appeal_pending_action'),
            models.UniqueConstraint(fields=['submitted_by', 'report'], condition=Q(status='pending', report__isnull=False), name='appeal_pending_report'),
        ]
        indexes = [models.Index(fields=['submitted_by', '-created_at'], name='appeal_owner_time'), models.Index(fields=['status', 'created_at'], name='appeal_review_queue')]
