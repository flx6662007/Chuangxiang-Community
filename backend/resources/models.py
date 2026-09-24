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

class ResourceTaxonomy(DomainModel):
    """受控分类、标签及研究/适用方向，不与现有赛事词条合表。"""
    immutable_fields = ('code', 'kind', 'name')
    code = models.SlugField('编码', max_length=64, unique=True)
    kind = models.CharField('用途', max_length=12, choices=[('category', 'category'), ('tag', 'tag'), ('direction', 'direction')])
    name = models.CharField('名称', max_length=80)
    is_active = models.BooleanField('可供新选择', default=True)
    sort_order = models.PositiveIntegerField('排序', default=0)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'ResourceTaxonomy'
        constraints = [
            models.UniqueConstraint(fields=['kind', 'name'], name='resourcetaxonomy_kind_name'),
            models.CheckConstraint(condition=Q(code__regex=r'\S'), name='s01_code_nonblank'),
            models.CheckConstraint(condition=Q(kind__in=['category', 'tag', 'direction']), name='s01_kind_enum'),
            models.CheckConstraint(condition=Q(kind__regex=r'\S'), name='s01_kind_nonblank'),
            models.CheckConstraint(condition=Q(name__regex=r'\S'), name='s01_name_nonblank'),
        ]
        indexes = [
            models.Index(fields=['kind', 'is_active', 'sort_order'], name='s01_idx_1'),
        ]


class Resource(DomainModel):
    """管理员维护的外链资源，无文件上传或托管字段。"""
    immutable_fields = ('code', 'created_at')
    code = models.SlugField('稳定编号', max_length=80, unique=True, default=new_code('resource'))
    title = models.CharField('资源名称', max_length=200)
    description = models.TextField('资源介绍', default='', blank=True, validators=[MaxLengthValidator(10000)])
    category = models.ForeignKey('resources.ResourceTaxonomy', verbose_name='资源类别', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    provider = models.CharField('来源单位或作者', max_length=500, default='', blank=True)
    access_url = models.URLField('访问链接', max_length=2048, default='', blank=True, validators=[URLValidator(schemes=['http','https'])])
    source_note = models.CharField('来源说明', max_length=1000, default='', blank=True)
    availability = models.CharField('可用状态', max_length=12, choices=[('available', 'available'), ('unavailable', 'unavailable')], default='available')
    last_verified_at = models.DateTimeField('最近实际核验时间', null=True, blank=True)
    publication_status = models.CharField('发布状态', max_length=12, choices=[('draft', 'draft'), ('published', 'published'), ('withdrawn', 'withdrawn')], default='draft')
    published_at = models.DateTimeField('首次发布时间', null=True, blank=True)
    last_edited_at = models.DateTimeField('最近内容编辑时间', null=True, blank=True)
    withdrawal_reason = models.CharField('最近下架原因', max_length=500, default='', blank=True)
    content_version = models.PositiveIntegerField('当前内容版本号', default=1, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField('建档时间', default=timezone.now)
    updated_at = models.DateTimeField('最近维护时间', auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='创建人', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='最近操作者', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    tags = models.ManyToManyField('resources.ResourceTaxonomy', through='resources.ResourceTag', blank=True, related_name='+')
    directions = models.ManyToManyField('resources.ResourceTaxonomy', through='resources.ResourceDirection', blank=True, related_name='+')
    competitions = models.ManyToManyField('competitions.Competition', through='resources.ResourceCompetition', blank=True, related_name='+')
    research_opportunities = models.ManyToManyField('research.ResearchOpportunity', through='resources.ResourceResearchOpportunity', blank=True, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'Resource'
        constraints = [
            models.CheckConstraint(condition=Q(publication_status='draft', published_at__isnull=True) | Q(publication_status__in=['published','withdrawn'], published_at__isnull=False), name='resource_pub_time'),
            models.CheckConstraint(condition=~Q(publication_status='withdrawn') | Q(withdrawal_reason__regex=r'\S'), name='resource_withdrawal'),
            models.CheckConstraint(condition=~Q(publication_status='published') | Q(title__regex=r'\S', description__regex=r'\S', category__isnull=False, access_url__regex=r'^https?://'), name='resource_required'),
            models.CheckConstraint(condition=Q(availability__in=['available', 'unavailable']), name='s02_availability_enum'),
            models.CheckConstraint(condition=Q(publication_status__in=['draft', 'published', 'withdrawn']), name='s02_publication_status_enum'),
            models.CheckConstraint(condition=Q(content_version__gte=1), name='s02_content_version_positive'),
        ]
        indexes = [
            models.Index(fields=['publication_status', 'availability', 'category'], name='s02_idx_1'),
        ]


class ResourceRevision(DomainModel):
    """资源内容及关系版本。"""
    immutable_fields = '*'
    resource = models.ForeignKey('resources.Resource', verbose_name='资源', on_delete=models.PROTECT, related_name='+')
    version = models.PositiveIntegerField('版本号', validators=[MinValueValidator(1)])
    snapshot = models.JSONField('内容快照', default=dict, blank=True)
    created_at = models.DateTimeField('版本时间', default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='操作者', on_delete=models.PROTECT, related_name='+', null=True, blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'ResourceRevision'
        constraints = [
            models.UniqueConstraint(fields=['resource', 'version'], name='resourcerevision_version'),
            models.CheckConstraint(condition=Q(version__gte=1), name='s03_version_positive'),
        ]
        indexes = [
        ]


class ResourceTag(DomainModel):
    """resources.Resource.tags 的显式关联。"""
    immutable_fields = '*'
    relation_owner = 'resource'
    relation_target = 'taxonomy'
    relation_kind = 'tag'
    resource = models.ForeignKey('resources.Resource', on_delete=models.CASCADE, related_name='+')
    taxonomy = models.ForeignKey('resources.ResourceTaxonomy', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        constraints = [models.UniqueConstraint(fields=['resource', 'taxonomy'], name='j09_unique_pair')]


class ResourceDirection(DomainModel):
    """resources.Resource.directions 的显式关联。"""
    immutable_fields = '*'
    relation_owner = 'resource'
    relation_target = 'taxonomy'
    relation_kind = 'direction'
    resource = models.ForeignKey('resources.Resource', on_delete=models.CASCADE, related_name='+')
    taxonomy = models.ForeignKey('resources.ResourceTaxonomy', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        constraints = [models.UniqueConstraint(fields=['resource', 'taxonomy'], name='j10_unique_pair')]


class ResourceCompetition(DomainModel):
    """resources.Resource.competitions 的显式关联。"""
    immutable_fields = '*'
    relation_owner = 'resource'
    relation_target = 'competition'
    relation_kind = None
    resource = models.ForeignKey('resources.Resource', on_delete=models.CASCADE, related_name='+')
    competition = models.ForeignKey('competitions.Competition', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        constraints = [models.UniqueConstraint(fields=['resource', 'competition'], name='j11_unique_pair')]


class ResourceResearchOpportunity(DomainModel):
    """resources.Resource.research_opportunities 的显式关联。"""
    immutable_fields = '*'
    relation_owner = 'resource'
    relation_target = 'opportunity'
    relation_kind = None
    resource = models.ForeignKey('resources.Resource', on_delete=models.CASCADE, related_name='+')
    opportunity = models.ForeignKey('research.ResearchOpportunity', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        constraints = [models.UniqueConstraint(fields=['resource', 'opportunity'], name='j12_unique_pair')]
