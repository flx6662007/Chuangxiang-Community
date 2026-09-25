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

class SourceConfig(DomainModel):
    """已获准接入的官方来源配置；采集调度由服务执行。"""
    code = models.CharField('来源编码', max_length=64, unique=True)
    name = models.CharField('来源名称', max_length=200)
    base_url = models.URLField('官方入口地址', max_length=2048, validators=[URLValidator(schemes=['http','https'])])
    content_kind = models.CharField('内容种类', max_length=20, choices=[('competition', 'competition'), ('research', 'research'), ('resource', 'resource'), ('mixed', 'mixed')])
    adapter_key = models.CharField('采集适配器标识', max_length=80)
    is_active = models.BooleanField('是否启用', default=False)
    created_at = models.DateTimeField('创建时间', default=timezone.now)
    updated_at = models.DateTimeField('维护时间', auto_now=True)
    maintained_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='维护人', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'SourceConfig'
        constraints = [
            models.CheckConstraint(condition=Q(code__regex=r'\S'), name='i01_code_nonblank'),
            models.CheckConstraint(condition=Q(name__regex=r'\S'), name='i01_name_nonblank'),
            models.CheckConstraint(condition=Q(content_kind__in=['competition', 'research', 'resource', 'mixed']), name='i01_content_kind_enum'),
            models.CheckConstraint(condition=Q(content_kind__regex=r'\S'), name='i01_content_kind_nonblank'),
            models.CheckConstraint(condition=Q(adapter_key__regex=r'\S'), name='i01_adapter_key_nonblank'),
        ]
        indexes = [
            models.Index(fields=['is_active', 'content_kind'], name='i01_idx_1'),
        ]


class FetchRun(DomainModel):
    """一次获准来源页面获取；批量任务可用同一 batch_key 关联多页。"""
    source = models.ForeignKey('ingestion.SourceConfig', verbose_name='来源配置', on_delete=models.PROTECT, related_name='+')
    batch_key = models.UUIDField('批次标识', default=uuid.uuid4)
    requested_url = models.URLField('实际请求地址', max_length=2048, validators=[URLValidator(schemes=['http','https'])])
    trigger = models.CharField('触发方式', max_length=12, choices=[('manual', 'manual'), ('scheduled', 'scheduled')])
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='手动触发人', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    status = models.CharField('运行状态', max_length=16, choices=[('running', 'running'), ('succeeded', 'succeeded'), ('unchanged', 'unchanged'), ('failed', 'failed')], default='running')
    started_at = models.DateTimeField('开始时间', default=timezone.now)
    finished_at = models.DateTimeField('结束时间', null=True, blank=True)
    http_status = models.PositiveSmallIntegerField('响应状态码', null=True, blank=True)
    error_code = models.CharField('错误码', max_length=80, default='', blank=True)
    error_summary = models.CharField('脱敏错误摘要', max_length=1000, default='', blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'FetchRun'
        constraints = [
            models.CheckConstraint(condition=Q(status='running', finished_at__isnull=True) | (Q(finished_at__isnull=False, finished_at__gte=F('started_at')) & ~Q(status='running')), name='fetchrun_finished'),
            models.CheckConstraint(condition=~Q(status='failed') | Q(error_code__regex=r'\S'), name='fetchrun_error'),
            models.CheckConstraint(condition=Q(http_status__isnull=True) | Q(http_status__gte=100, http_status__lte=599), name='fetchrun_http'),
            models.CheckConstraint(condition=Q(trigger='manual', triggered_by__isnull=False) | Q(trigger='scheduled', triggered_by__isnull=True), name='fetchrun_trigger_user'),
            models.CheckConstraint(condition=Q(trigger__in=['manual', 'scheduled']), name='i02_trigger_enum'),
            models.CheckConstraint(condition=Q(trigger__regex=r'\S'), name='i02_trigger_nonblank'),
            models.CheckConstraint(condition=Q(status__in=['running', 'succeeded', 'unchanged', 'failed']), name='i02_status_enum'),
        ]
        indexes = [
            models.Index(fields=['source', 'started_at'], name='i02_idx_1'),
            models.Index(fields=['status', 'finished_at'], name='i02_idx_2'),
            models.Index(fields=['batch_key'], name='i02_idx_3'),
        ]


class SourceVersion(DomainModel):
    """来源页面文本的一次不可变内容版本。"""
    immutable_fields = ('source_id', 'first_fetch_id', 'source_url', 'title', 'body_text', 'content_hash', 'source_published_on', 'source_updated_on', 'source_time_text', 'first_seen_at')
    source = models.ForeignKey('ingestion.SourceConfig', verbose_name='来源配置', on_delete=models.PROTECT, related_name='+')
    first_fetch = models.ForeignKey('ingestion.FetchRun', verbose_name='首次获取记录', on_delete=models.PROTECT, related_name='+')
    source_url = models.URLField('原文地址', max_length=2048, validators=[URLValidator(schemes=['http','https'])])
    title = models.CharField('原文标题', max_length=500, default='', blank=True)
    body_text = models.TextField('提取的原文文本', validators=[MaxLengthValidator(200000)])
    content_hash = models.CharField('规范化文本 SHA-256', max_length=64)
    source_published_on = models.DateField('来源发布日期', null=True, blank=True)
    source_updated_on = models.DateField('来源更新日期', null=True, blank=True)
    source_time_text = models.CharField('不完整时间原文', max_length=500, default='', blank=True)
    first_seen_at = models.DateTimeField('首次获取时间', default=timezone.now)
    last_seen_at = models.DateTimeField('最后重见时间', default=timezone.now)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'SourceVersion'
        constraints = [
            models.UniqueConstraint(fields=['source', 'source_url', 'content_hash'], name='sourceversion_content'),
            models.CheckConstraint(condition=Q(last_seen_at__gte=F('first_seen_at')), name='sourceversion_seen_order'),
            models.CheckConstraint(condition=Q(content_hash__regex=r'^[a-f0-9]{64}$'), name='sourceversion_hash'),
        ]
        indexes = [
            models.Index(fields=['source', 'source_url'], name='i03_idx_1'),
            models.Index(fields=['content_hash'], name='i03_idx_2'),
        ]


class ProcessingResult(DomainModel):
    """一次提取或快讯草稿生成的候选结果及审核决定。"""
    task_type = models.CharField('任务类型', max_length=32, choices=[('competition_extract', 'competition_extract'), ('research_extract', 'research_extract'), ('newsletter_draft', 'newsletter_draft')])
    source_version = models.ForeignKey('ingestion.SourceVersion', verbose_name='提取原文版本', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    ai_call = models.ForeignKey('ingestion.AICall', verbose_name='关联 AI 调用', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    candidate = models.JSONField('候选字段或条目', default=dict, blank=True)
    evidence = models.JSONField('字段/条目原文依据', default=dict, blank=True)
    missing_fields = models.JSONField('缺失字段名', default=list, blank=True)
    validation_errors = models.JSONField('校验错误', default=list, blank=True)
    status = models.CharField('处理状态', max_length=12, choices=[('pending', 'pending'), ('accepted', 'accepted'), ('rejected', 'rejected')], default='pending')
    decision_mode = models.CharField('决定方式', max_length=12, choices=[('', '未填写'), ('human', 'human'), ('rules', 'rules')], default='', blank=True)
    rule_version = models.CharField('受控规则版本', max_length=80, default='', blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='确认管理员', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    reviewed_at = models.DateTimeField('作出决定时间', null=True, blank=True)
    created_at = models.DateTimeField('生成时间', default=timezone.now)
    competition = models.ForeignKey('competitions.Competition', verbose_name='采纳后的赛事', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    research = models.ForeignKey('research.ResearchOpportunity', verbose_name='采纳后的科研', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    newsletter_revision = models.ForeignKey('newsletters.NewsletterRevision', verbose_name='采纳后的快讯草稿版本', on_delete=models.PROTECT, related_name='+', null=True, blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'ProcessingResult'
        constraints = [
            models.CheckConstraint(condition=Q(task_type='newsletter_draft', source_version__isnull=True) | Q(task_type__in=['competition_extract','research_extract'], source_version__isnull=False), name='processingresult_input'),
            models.CheckConstraint(condition=Q(status='pending', decision_mode='', reviewed_at__isnull=True, reviewed_by__isnull=True, rule_version='') | (Q(status__in=['accepted','rejected'], decision_mode='human', reviewed_at__isnull=False, reviewed_by__isnull=False, rule_version='')) | (Q(status='accepted', task_type='competition_extract', decision_mode='rules', reviewed_at__isnull=False, reviewed_by__isnull=True) & ~Q(rule_version='')), name='processingresult_decision'),
            models.CheckConstraint(condition=(~Q(status='accepted') & Q(competition__isnull=True, research__isnull=True, newsletter_revision__isnull=True)) | Q(status='accepted', task_type='competition_extract', competition__isnull=False, research__isnull=True, newsletter_revision__isnull=True) | Q(status='accepted', task_type='research_extract', competition__isnull=True, research__isnull=False, newsletter_revision__isnull=True) | Q(status='accepted', task_type='newsletter_draft', competition__isnull=True, research__isnull=True, newsletter_revision__isnull=False), name='processingresult_target'),
            models.CheckConstraint(condition=Q(task_type__in=['competition_extract', 'research_extract', 'newsletter_draft']), name='i04_task_type_enum'),
            models.CheckConstraint(condition=Q(task_type__regex=r'\S'), name='i04_task_type_nonblank'),
            models.CheckConstraint(condition=Q(status__in=['pending', 'accepted', 'rejected']), name='i04_status_enum'),
            models.CheckConstraint(condition=Q(decision_mode__in=['', 'human', 'rules']), name='i04_decision_mode_enum'),
        ]
        indexes = [
            models.Index(fields=['status', 'created_at'], name='i04_idx_1'),
            models.Index(fields=['source_version', 'created_at'], name='i04_idx_2'),
            models.Index(fields=['task_type', 'status'], name='i04_idx_3'),
        ]


class ProcessingInput(DomainModel):
    """快讯生成时冻结的已核验业务输入，保障事后核对来源。"""
    immutable_fields = '*'
    result = models.ForeignKey('ingestion.ProcessingResult', verbose_name='所属快讯处理结果', on_delete=models.PROTECT, related_name='+')
    position = models.PositiveIntegerField('输入次序', validators=[MinValueValidator(1)])
    competition = models.ForeignKey('competitions.Competition', verbose_name='赛事输入', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    research = models.ForeignKey('research.ResearchOpportunity', verbose_name='科研输入', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    resource = models.ForeignKey('resources.Resource', verbose_name='资源输入', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    snapshot = models.JSONField('输入白名单快照', default=dict, blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'ProcessingInput'
        constraints = [
            models.CheckConstraint(condition=Q(competition__isnull=False, research__isnull=True, resource__isnull=True) | Q(competition__isnull=True, research__isnull=False, resource__isnull=True) | Q(competition__isnull=True, research__isnull=True, resource__isnull=False), name='processinginput_target'),
            models.UniqueConstraint(fields=['result', 'position'], name='processinginput_position'),
            models.CheckConstraint(condition=Q(position__gte=1), name='i05_position_positive'),
        ]
        indexes = [
        ]


class AICall(DomainModel):
    """一次模型调用的必要运行日志；不在现有 ai_services 服务包内定义 ORM 模型。"""
    trace_key = models.UUIDField('请求/重试链标识', default=uuid.uuid4)
    provider = models.CharField('服务商', max_length=50)
    model_name = models.CharField('实际模型', max_length=200)
    prompt_version = models.CharField('提示词版本', max_length=80)
    started_at = models.DateTimeField('调用开始', default=timezone.now)
    finished_at = models.DateTimeField('调用结束', null=True, blank=True)
    status = models.CharField('状态', max_length=12, choices=[('running', 'running'), ('succeeded', 'succeeded'), ('failed', 'failed')], default='running')
    duration_ms = models.PositiveBigIntegerField('耗时毫秒', null=True, blank=True)
    input_tokens = models.PositiveBigIntegerField('输入 token', null=True, blank=True)
    output_tokens = models.PositiveBigIntegerField('输出 token', null=True, blank=True)
    error_code = models.CharField('错误码', max_length=80, default='', blank=True)
    error_summary = models.CharField('脱敏错误摘要', max_length=1000, default='', blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'AICall'
        constraints = [
            models.CheckConstraint(condition=Q(status='running', finished_at__isnull=True) | (Q(finished_at__isnull=False, finished_at__gte=F('started_at')) & ~Q(status='running')), name='aicall_finished'),
            models.CheckConstraint(condition=~Q(status='failed') | Q(error_code__regex=r'\S'), name='aicall_error'),
            models.CheckConstraint(condition=Q(status='running', duration_ms__isnull=True) | (Q(duration_ms__isnull=False) & ~Q(status='running')), name='aicall_duration'),
            models.CheckConstraint(condition=Q(provider__regex=r'\S'), name='i06_provider_nonblank'),
            models.CheckConstraint(condition=Q(model_name__regex=r'\S'), name='i06_model_name_nonblank'),
            models.CheckConstraint(condition=Q(prompt_version__regex=r'\S'), name='i06_prompt_version_nonblank'),
            models.CheckConstraint(condition=Q(status__in=['running', 'succeeded', 'failed']), name='i06_status_enum'),
        ]
        indexes = [
            models.Index(fields=['trace_key'], name='i06_idx_1'),
            models.Index(fields=['status', 'finished_at'], name='i06_idx_2'),
        ]
