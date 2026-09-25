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

class ResearchTaxonomy(DomainModel):
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
        verbose_name = 'ResearchTaxonomy'
        constraints = [
            models.UniqueConstraint(fields=['kind', 'name'], name='researchtaxonomy_kind_name'),
            models.CheckConstraint(condition=Q(code__regex=r'\S'), name='r01_code_nonblank'),
            models.CheckConstraint(condition=Q(kind__in=['category', 'tag', 'direction']), name='r01_kind_enum'),
            models.CheckConstraint(condition=Q(kind__regex=r'\S'), name='r01_kind_nonblank'),
            models.CheckConstraint(condition=Q(name__regex=r'\S'), name='r01_name_nonblank'),
        ]
        indexes = [
            models.Index(fields=['kind', 'is_active', 'sort_order'], name='r01_idx_1'),
        ]


class ResearchOpportunity(DomainModel):
    """一次具体科研招募。人工发布必填仅为基本信息、招募主体、官方信息链接。"""
    immutable_fields = ('code', 'created_at')
    code = models.SlugField('稳定编号', max_length=80, unique=True, default=new_code('research'))
    title = models.CharField('标题', max_length=200)
    description = models.TextField('基本介绍/原文说明', default='', blank=True, validators=[MaxLengthValidator(20000)])
    summary = models.CharField('列表短摘要', max_length=500, default='', blank=True)
    recruiting_entity = models.CharField('招募主体原文', max_length=1000, default='', blank=True)
    official_url = models.URLField('官方信息链接', max_length=2048, default='', blank=True, validators=[URLValidator(schemes=['http','https'])])
    official_source_name = models.CharField('官方来源名称', max_length=200, default='', blank=True)
    supervisor = models.CharField('可提取的导师名称', max_length=200, default='', blank=True)
    research_group = models.CharField('可提取的课题组/实验室', max_length=200, default='', blank=True)
    institution = models.CharField('可提取的院系/机构', max_length=200, default='', blank=True)
    category = models.ForeignKey('research.ResearchTaxonomy', verbose_name='可选分类', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    work_content = models.TextField('独立工作内容', default='', blank=True, validators=[MaxLengthValidator(5000)])
    eligibility = models.TextField('面向对象', default='', blank=True, validators=[MaxLengthValidator(5000)])
    requirements = models.TextField('能力要求', default='', blank=True, validators=[MaxLengthValidator(5000)])
    vacancies_text = models.CharField('名额原文', max_length=500, default='', blank=True)
    vacancies_min = models.PositiveIntegerField('有依据的最少名额', null=True, blank=True)
    vacancies_max = models.PositiveIntegerField('有依据的最多名额', null=True, blank=True)
    weekly_hours_text = models.CharField('投入原文', max_length=500, default='', blank=True)
    weekly_hours_min = models.DecimalField('每周最低小时数', max_digits=5, decimal_places=2, null=True, blank=True)
    weekly_hours_max = models.DecimalField('每周最高小时数', max_digits=5, decimal_places=2, null=True, blank=True)
    duration_text = models.CharField('合作周期原文', max_length=500, default='', blank=True)
    starts_on = models.DateField('明确开始日期', null=True, blank=True)
    ends_on = models.DateField('明确结束日期', null=True, blank=True)
    collaboration_mode = models.CharField('协作方式', max_length=12, choices=[('unknown', 'unknown'), ('online', 'online'), ('offline', 'offline'), ('hybrid', 'hybrid')], default='unknown')
    location_text = models.CharField('地点原文', max_length=500, default='', blank=True)
    application_instructions = models.TextField('申请说明', default='', blank=True, validators=[MaxLengthValidator(5000)])
    application_url = models.URLField('可选独立报名链接', max_length=2048, default='', blank=True, validators=[URLValidator(schemes=['http','https'])])
    application_email = models.EmailField('可选公开申请邮箱', max_length=254, default='', blank=True)
    deadline_mode = models.CharField('截止类型', max_length=12, choices=[('unknown', 'unknown'), ('fixed', 'fixed'), ('ongoing', 'ongoing')], default='unknown')
    deadline_on = models.DateField('截止日期', null=True, blank=True)
    deadline_at = models.DateTimeField('精确截止时刻', null=True, blank=True)
    deadline_timezone = models.CharField('来源时区', max_length=64, default='', blank=True)
    deadline_notes = models.CharField('截止原文与例外', max_length=1000, default='', blank=True)
    closed_at = models.DateTimeField('核实结束时间', null=True, blank=True)
    closure_note = models.CharField('结束说明', max_length=500, default='', blank=True)
    last_verified_at = models.DateTimeField('最近实际核验时间', null=True, blank=True)
    verification_note = models.TextField('内部核验说明', default='', blank=True, validators=[MaxLengthValidator(2000)])
    publication_status = models.CharField('发布状态', max_length=12, choices=[('draft', 'draft'), ('published', 'published'), ('withdrawn', 'withdrawn')], default='draft')
    published_at = models.DateTimeField('首次发布时间', null=True, blank=True)
    last_edited_at = models.DateTimeField('最近内容编辑时间', null=True, blank=True)
    withdrawal_reason = models.CharField('最近下架原因', max_length=500, default='', blank=True)
    content_version = models.PositiveIntegerField('当前内容版本号', default=1, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField('建档时间', default=timezone.now)
    updated_at = models.DateTimeField('最近维护时间', auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='创建人', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='最近操作者', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    tags = models.ManyToManyField('research.ResearchTaxonomy', through='research.ResearchTag', blank=True, related_name='+')
    directions = models.ManyToManyField('research.ResearchTaxonomy', through='research.ResearchDirection', blank=True, related_name='+')

    @property
    def is_closed(self):
        if self.closed_at:
            return True
        if self.deadline_at:
            return self.deadline_at <= timezone.now()
        return bool(self.deadline_on and self.deadline_on < timezone.localdate())

    @property
    def needs_reverification(self):
        basis = self.last_verified_at or self.published_at
        return bool(self.publication_status == 'published' and not self.is_closed
                    and self.deadline_mode in ['unknown','ongoing'] and basis
                    and basis + timedelta(days=30) <= timezone.now())

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'ResearchOpportunity'
        constraints = [
            models.CheckConstraint(condition=Q(publication_status='draft', published_at__isnull=True) | Q(publication_status__in=['published','withdrawn'], published_at__isnull=False), name='researchopportuni_pub_time'),
            models.CheckConstraint(condition=~Q(publication_status='withdrawn') | Q(withdrawal_reason__regex=r'\S'), name='researchopportuni_withdrawal'),
            models.CheckConstraint(condition=~Q(publication_status='published') | Q(title__regex=r'\S',description__regex=r'\S',recruiting_entity__regex=r'\S',official_url__regex=r'^https?://'), name='researchopportuni_required'),
            models.CheckConstraint(condition=Q(deadline_mode='fixed', deadline_on__isnull=False) | Q(deadline_mode__in=['unknown','ongoing'], deadline_on__isnull=True, deadline_at__isnull=True, deadline_timezone=''), name='researchopportuni_deadline'),
            models.CheckConstraint(condition=Q(deadline_at__isnull=True, deadline_timezone='') | (Q(deadline_at__isnull=False, deadline_on__isnull=False) & ~Q(deadline_timezone='')), name='researchopportuni_time_pair'),
            models.CheckConstraint(condition=Q(vacancies_min__isnull=True) | Q(vacancies_max__isnull=True) | Q(vacancies_min__lte=F('vacancies_max')), name='researchopportuni_vacancie_order'),
            models.CheckConstraint(condition=Q(weekly_hours_min__isnull=True) | Q(weekly_hours_max__isnull=True) | Q(weekly_hours_min__lte=F('weekly_hours_max')), name='researchopportuni_weekly_h_order'),
            models.CheckConstraint(condition=Q(starts_on__isnull=True) | Q(ends_on__isnull=True) | Q(starts_on__lte=F('ends_on')), name='researchopportuni_starts_o_order'),
            models.CheckConstraint(condition=Q(weekly_hours_min__isnull=True) | Q(weekly_hours_min__gte=0, weekly_hours_min__lte=168), name='researchopportuni_min_hours'),
            models.CheckConstraint(condition=Q(weekly_hours_max__isnull=True) | Q(weekly_hours_max__gte=0, weekly_hours_max__lte=168), name='researchopportuni_max_hours'),
            models.CheckConstraint(condition=Q(collaboration_mode__in=['unknown', 'online', 'offline', 'hybrid']), name='r02_collaboration_mode_enum'),
            models.CheckConstraint(condition=Q(deadline_mode__in=['unknown', 'fixed', 'ongoing']), name='r02_deadline_mode_enum'),
            models.CheckConstraint(condition=Q(publication_status__in=['draft', 'published', 'withdrawn']), name='r02_publication_status_enum'),
            models.CheckConstraint(condition=Q(content_version__gte=1), name='r02_content_version_positive'),
        ]
        indexes = [
            models.Index(fields=['publication_status', 'deadline_mode', 'deadline_on'], name='r02_idx_2'),
            models.Index(fields=['category', 'publication_status'], name='r02_idx_3'),
            models.Index(fields=['last_verified_at'], name='r02_idx_4'),
        ]


class ResearchSource(DomainModel):
    """官方信息链接之外的补充来源；主链接唯一来源在主表 official_url，不建立第二份可编辑副本。"""
    opportunity = models.ForeignKey('research.ResearchOpportunity', verbose_name='科研机会', on_delete=models.PROTECT, related_name='+')
    source_url = models.URLField('补充链接', max_length=2048, validators=[URLValidator(schemes=['http','https'])])
    source_name = models.CharField('来源名称', max_length=200, default='', blank=True)
    source_type = models.CharField('来源类型', max_length=16, choices=[('unknown', 'unknown'), ('official', 'official'), ('campus', 'campus')], default='unknown')
    published_on = models.DateField('来源发布日期', null=True, blank=True)
    updated_on = models.DateField('来源更新日期', null=True, blank=True)
    fetched_at = models.DateTimeField('最近获取时间', null=True, blank=True)
    verified_at = models.DateTimeField('来源核验时间', null=True, blank=True)
    created_at = models.DateTimeField('记录时间', default=timezone.now)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'ResearchSource'
        constraints = [
            models.UniqueConstraint(fields=['opportunity', 'source_url'], name='researchsource_url'),
            models.CheckConstraint(condition=Q(source_type__in=['unknown', 'official', 'campus']), name='r03_source_type_enum'),
        ]
        indexes = [
            models.Index(fields=['opportunity', 'created_at'], name='r03_idx_1'),
        ]


class ResearchRevision(DomainModel):
    """科研每个内容版本的完整快照，供追溯与快讯差异提示。"""
    immutable_fields = '*'
    opportunity = models.ForeignKey('research.ResearchOpportunity', verbose_name='科研机会', on_delete=models.PROTECT, related_name='+')
    version = models.PositiveIntegerField('版本号', validators=[MinValueValidator(1)])
    snapshot = models.JSONField('该版完整内容', default=dict, blank=True)
    created_at = models.DateTimeField('版本时间', default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='操作者', on_delete=models.PROTECT, related_name='+', null=True, blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'ResearchRevision'
        constraints = [
            models.UniqueConstraint(fields=['opportunity', 'version'], name='researchrevision_version'),
            models.CheckConstraint(condition=Q(version__gte=1), name='r04_version_positive'),
        ]
        indexes = [
        ]


class ResearchTag(DomainModel):
    """research.ResearchOpportunity.tags 的显式关联。"""
    immutable_fields = '*'
    relation_owner = 'opportunity'
    relation_target = 'taxonomy'
    relation_kind = 'tag'
    opportunity = models.ForeignKey('research.ResearchOpportunity', on_delete=models.CASCADE, related_name='+')
    taxonomy = models.ForeignKey('research.ResearchTaxonomy', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        constraints = [models.UniqueConstraint(fields=['opportunity', 'taxonomy'], name='j07_unique_pair')]


class ResearchDirection(DomainModel):
    """research.ResearchOpportunity.directions 的显式关联。"""
    immutable_fields = '*'
    relation_owner = 'opportunity'
    relation_target = 'taxonomy'
    relation_kind = 'direction'
    opportunity = models.ForeignKey('research.ResearchOpportunity', on_delete=models.CASCADE, related_name='+')
    taxonomy = models.ForeignKey('research.ResearchTaxonomy', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        constraints = [models.UniqueConstraint(fields=['opportunity', 'taxonomy'], name='j08_unique_pair')]
