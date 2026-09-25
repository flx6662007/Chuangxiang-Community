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

class Newsletter(DomainModel):
    """一期快讯的稳定身份和公开版本指针；编辑新草稿不改变已公开内容。"""
    immutable_fields = ('code', 'created_at')
    code = models.SlugField('稳定编号', max_length=80, unique=True, default=new_code('newsletter'))
    publication_status = models.CharField('发布状态', max_length=12, choices=[('draft', 'draft'), ('published', 'published'), ('withdrawn', 'withdrawn')], default='draft')
    current_revision = models.ForeignKey('newsletters.NewsletterRevision', verbose_name='当前公开版本', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    published_at = models.DateTimeField('首次发布时间', null=True, blank=True)
    last_edited_at = models.DateTimeField('最后公开更正时间', null=True, blank=True)
    withdrawal_reason = models.CharField('下架原因', max_length=500, default='', blank=True)
    created_at = models.DateTimeField('创建时间', default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='创建人', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'Newsletter'
        constraints = [
            models.CheckConstraint(condition=Q(publication_status='draft', published_at__isnull=True) | Q(publication_status__in=['published','withdrawn'], published_at__isnull=False), name='newsletter_pub_time'),
            models.CheckConstraint(condition=~Q(publication_status='withdrawn') | Q(withdrawal_reason__regex=r'\S'), name='newsletter_withdrawal'),
            models.CheckConstraint(condition=~Q(publication_status='published') | Q(current_revision__isnull=False), name='newsletter_revision'),
            models.CheckConstraint(condition=Q(publication_status__in=['draft', 'published', 'withdrawn']), name='n01_publication_status_enum'),
        ]
        indexes = [
            models.Index(fields=['publication_status', 'published_at'], name='n01_idx_1'),
        ]


class NewsletterRevision(DomainModel):
    """一期快讯的草稿或已确认版本；已经确认的版本不可改写。"""
    newsletter = models.ForeignKey('newsletters.Newsletter', verbose_name='所属快讯', on_delete=models.PROTECT, related_name='+')
    version = models.PositiveIntegerField('版本号', validators=[MinValueValidator(1)])
    title = models.CharField('标题', max_length=200, default='', blank=True)
    introduction = models.TextField('导读', default='', blank=True, validators=[MaxLengthValidator(5000)])
    status = models.CharField('版本状态', max_length=12, choices=[('draft', 'draft'), ('confirmed', 'confirmed')], default='draft')
    created_at = models.DateTimeField('草稿创建时间', default=timezone.now)
    updated_at = models.DateTimeField('草稿更新时间', auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='创建人', on_delete=models.PROTECT, related_name='+')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='编辑人', on_delete=models.PROTECT, related_name='+')
    confirmed_at = models.DateTimeField('管理员确认时间', null=True, blank=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='确认管理员', on_delete=models.PROTECT, related_name='+', null=True, blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'NewsletterRevision'
        constraints = [
            models.UniqueConstraint(fields=['newsletter', 'version'], name='newsletterrevisio_version'),
            models.UniqueConstraint(fields=['newsletter'], name='newsletterrevisio_one_draft', condition=Q(status='draft')),
            models.CheckConstraint(condition=Q(status='draft', confirmed_at__isnull=True, confirmed_by__isnull=True) | Q(status='confirmed', confirmed_at__isnull=False, confirmed_by__isnull=False, title__regex=r'\S'), name='newsletterrevisio_confirmed'),
            models.CheckConstraint(condition=Q(version__gte=1), name='n02_version_positive'),
            models.CheckConstraint(condition=Q(status__in=['draft', 'confirmed']), name='n02_status_enum'),
        ]
        indexes = [
            models.Index(fields=['newsletter', 'status'], name='n02_idx_2'),
        ]


class NewsletterItem(DomainModel):
    """某快讯版本中的一个内容项；活动只存在于该表。"""
    revision = models.ForeignKey('newsletters.NewsletterRevision', verbose_name='所属快讯版本', on_delete=models.PROTECT, related_name='+')
    position = models.PositiveIntegerField('排序', validators=[MinValueValidator(1)])
    kind = models.CharField('条目类型', max_length=16, choices=[('competition', 'competition'), ('research', 'research'), ('resource', 'resource'), ('activity', 'activity')])
    competition = models.ForeignKey('competitions.Competition', verbose_name='赛事引用', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    research = models.ForeignKey('research.ResearchOpportunity', verbose_name='科研引用', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    resource = models.ForeignKey('resources.Resource', verbose_name='资源引用', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    title_snapshot = models.CharField('当期标题', max_length=200)
    summary_snapshot = models.TextField('当期摘要/活动介绍', default='', blank=True, validators=[MaxLengthValidator(5000)])
    source_url = models.URLField('当期来源链接', max_length=2048, validators=[URLValidator(schemes=['http','https'])])
    source_updated_at = models.DateTimeField('引用时业务内容时间', null=True, blank=True)
    source_version = models.PositiveIntegerField('引用时业务版本', null=True, blank=True)
    activity_time_text = models.CharField('活动时间原文', max_length=500, default='', blank=True)
    activity_location_text = models.CharField('活动地点原文', max_length=500, default='', blank=True)

    @property
    def is_publicly_visible(self):
        if self.revision.status != 'confirmed' or self.revision.newsletter.publication_status != 'published':
            return False
        return self.kind == 'activity' or getattr(self, self.kind).publication_status == 'published'

    @property
    def source_has_updates(self):
        if self.kind == 'competition':
            return self.source_updated_at != self.competition.updated_at
        if self.kind in ['research','resource']:
            return self.source_version != getattr(self, self.kind).content_version
        return False

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'NewsletterItem'
        constraints = [
            models.UniqueConstraint(fields=['revision', 'position'], name='newsletteritem_position'),
            models.CheckConstraint(condition=Q(kind='competition', competition__isnull=False, research__isnull=True, resource__isnull=True) | Q(kind='research', competition__isnull=True, research__isnull=False, resource__isnull=True) | Q(kind='resource', competition__isnull=True, research__isnull=True, resource__isnull=False) | Q(kind='activity', competition__isnull=True, research__isnull=True, resource__isnull=True), name='newsletteritem_target'),
            models.CheckConstraint(condition=Q(kind='activity') | Q(activity_time_text='', activity_location_text=''), name='newsletteritem_activity'),
            models.CheckConstraint(condition=Q(position__gte=1), name='n03_position_positive'),
            models.CheckConstraint(condition=Q(kind__in=['competition', 'research', 'resource', 'activity']), name='n03_kind_enum'),
            models.CheckConstraint(condition=Q(kind__regex=r'\S'), name='n03_kind_nonblank'),
            models.CheckConstraint(condition=Q(title_snapshot__regex=r'\S'), name='n03_title_snapshot_nonblank'),
        ]
        indexes = [
        ]
