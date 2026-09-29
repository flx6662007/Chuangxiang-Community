from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class CatalogEntry(models.Model):
    code = models.CharField('目录编号', max_length=16, unique=True)
    version = models.PositiveSmallIntegerField('目录年份', default=2026)
    name = models.CharField('目录原名', max_length=300)
    grade = models.CharField('目录等级', max_length=8)
    levels = models.CharField('目录赛事级别', max_length=100)
    departments = models.JSONField('责任学院', default=list)
    aliases = models.JSONField('已核实名称别名', default=list, blank=True)
    is_active = models.BooleanField('纳入当前范围', default=True)
    source_url = models.URLField('目录依据', max_length=2048)

    class Meta:
        ordering = ['code']
        verbose_name = '学校赛事目录'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.code} {self.name}'


class OfficialSite(models.Model):
    entry = models.ForeignKey(CatalogEntry, on_delete=models.PROTECT, related_name='sites')
    url = models.URLField('监测入口', max_length=2048)
    evidence_url = models.URLField('官网关联依据', max_length=2048)
    kind = models.CharField('来源类型', max_length=24, default='competition', choices=[
        ('competition', '赛事官网'), ('organizer', '主办方官网'), ('campus', '校内官方通知'),
    ])
    dedicated = models.BooleanField('赛事专站', default=False)
    allowed_hosts = models.JSONField('已核对域名', default=list)
    note = models.CharField('接入说明', max_length=1000, blank=True)
    enabled = models.BooleanField('启用监测', default=True)
    last_checked_at = models.DateTimeField('最近尝试', null=True, blank=True)
    last_success_at = models.DateTimeField('最近成功', null=True, blank=True)
    next_check_at = models.DateTimeField('下次检查', null=True, blank=True)
    last_status = models.CharField('最近状态', max_length=32, default='never')
    last_error = models.CharField('最近问题', max_length=1000, blank=True)
    consecutive_failures = models.PositiveSmallIntegerField(default=0, editable=False)
    page_attempts = models.JSONField('页面轮换记录', default=dict, editable=False)

    class Meta:
        ordering = ['entry__code', 'pk']
        constraints = [models.UniqueConstraint(fields=['entry', 'url'], name='catalog_site_unique')]
        verbose_name = '官网监测入口'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.entry.code} {self.url}'


class OfficialNotice(models.Model):
    site = models.ForeignKey(OfficialSite, on_delete=models.PROTECT, related_name='notices')
    url = models.URLField('原文地址', max_length=2048)
    title = models.CharField('原文标题', max_length=500)
    page_kind = models.CharField('页面类型', max_length=16, default='notice', choices=[('notice', '通知'), ('index', '入口快照')])
    body = models.TextField('原文文本')
    content_hash = models.CharField(max_length=64, editable=False)
    attachments = models.JSONField('附件链接（未解析）', default=list, blank=True)
    source_published_on = models.DateField('原文明确发布日期', null=True, blank=True)
    first_seen_at = models.DateTimeField('首次发现', auto_now_add=True)
    last_seen_at = models.DateTimeField('最近成功读取', auto_now_add=True)
    is_current_version = models.BooleanField('当前原文版本', default=True)
    status = models.CharField('处理状态', max_length=32, default='pending', choices=[
        ('pending', '待提取核对'), ('attachment', '关键内容在附件'), ('historical', '往届资料'),
    ])

    class Meta:
        ordering = ['-last_seen_at']
        constraints = [models.UniqueConstraint(fields=['site', 'url', 'content_hash'], name='catalog_notice_version_unique')]
        verbose_name = '官网通知原文'
        verbose_name_plural = verbose_name


class MonitorRun(models.Model):
    site = models.ForeignKey(OfficialSite, on_delete=models.PROTECT, related_name='runs')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=32, default='running')
    pages = models.PositiveSmallIntegerField(default=0)
    created = models.PositiveSmallIntegerField(default=0)
    unchanged = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ['-started_at']
        verbose_name = '官网监测记录'
        verbose_name_plural = verbose_name


class CatalogBinding(models.Model):
    entry = models.ForeignKey(CatalogEntry, on_delete=models.PROTECT, related_name='competition_bindings')
    competition = models.ForeignKey('competitions.Competition', on_delete=models.PROTECT, related_name='catalog_bindings')
    basis = models.CharField('赛事归属依据', max_length=1000)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['entry', 'competition'], name='catalog_competition_unique')]
        verbose_name = '已发布赛事目录关联'
        verbose_name_plural = verbose_name


class CatalogExtraction(models.Model):
    """提取结果绑定不可变原文；普通后台不能编辑候选冒充核验。"""

    notice = models.ForeignKey(OfficialNotice, on_delete=models.PROTECT, related_name='extractions')
    source_hash = models.CharField('提取时原文哈希', max_length=64, editable=False)
    candidate = models.JSONField('字段候选', default=dict, blank=True)
    evidence = models.JSONField('字段原文依据', default=dict, blank=True)
    missing_fields = models.JSONField('缺少字段', default=list, blank=True)
    errors = models.JSONField('提取错误', default=list, blank=True)
    rule_version = models.CharField('提取规则版本', max_length=100)
    disposition = models.CharField('提取结论', max_length=16, choices=[
        ('ready', '可进一步核验发布'), ('review', '待补充核对'),
        ('irrelevant', '非赛事报名通知'), ('historical', '历史赛事'),
    ])
    status = models.CharField('处理状态', max_length=16, default='pending', choices=[
        ('pending', '待处理'), ('published', '已关联发布'), ('rejected', '已拒绝'),
    ])
    competition = models.ForeignKey(
        'competitions.Competition', on_delete=models.PROTECT, null=True, blank=True,
        related_name='catalog_extractions', verbose_name='已发布赛事',
    )
    decision_mode = models.CharField('处理方式', max_length=16, blank=True, default='',
                                     choices=[('rules', '规则复核'), ('human', '管理员复核')])
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='reviewed_catalog_extractions', verbose_name='维护身份',
    )
    reviewed_at = models.DateTimeField('处理时间', null=True, blank=True)
    review_note = models.CharField('处理说明', max_length=1000, blank=True, default='')
    created_at = models.DateTimeField('提取时间', auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = '官网赛事提取'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(fields=['notice', 'rule_version'], name='catalog_extraction_version_unique'),
            models.CheckConstraint(condition=Q(disposition__in=['ready', 'review', 'irrelevant', 'historical']),
                                   name='catalog_extraction_disposition'),
            models.CheckConstraint(
                condition=Q(status='pending', competition__isnull=True, reviewed_by__isnull=True,
                            reviewed_at__isnull=True, decision_mode='')
                | Q(status='published', competition__isnull=False, reviewed_by__isnull=False,
                    reviewed_at__isnull=False, decision_mode__in=['rules', 'human'])
                | Q(status='rejected', competition__isnull=True, reviewed_by__isnull=False,
                    reviewed_at__isnull=False, decision_mode='human'),
                name='catalog_extraction_decision_pair',
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        for field in ('candidate', 'evidence'):
            if not isinstance(getattr(self, field), dict):
                errors[field] = '必须是字段对象。'
        for field in ('missing_fields', 'errors'):
            value = getattr(self, field)
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                errors[field] = '必须是文字列表。'
        if self.pk:
            old = type(self).objects.get(pk=self.pk)
            immutable = ('notice_id', 'source_hash', 'candidate', 'evidence',
                         'missing_fields', 'errors', 'rule_version', 'disposition')
            if any(getattr(self, field) != getattr(old, field) for field in immutable):
                errors['candidate'] = '原文及提取结果不可改写；修正规则后使用新版本重新提取。'
            if old.status != 'pending' and any(getattr(self, field) != getattr(old, field) for field in
                    ('status', 'competition_id', 'decision_mode', 'reviewed_by_id', 'reviewed_at')):
                errors['status'] = '已处理结论不能覆盖。'
        if errors:
            raise ValidationError(errors)
