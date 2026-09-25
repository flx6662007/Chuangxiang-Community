"""赛事届次、来源与受控词条；写入服务须在保存前执行 full_clean。"""

from datetime import date, datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinValueValidator, URLValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from .validators import parse_source_timezone, validate_code, validate_source_timezone


def nonblank_constraint(field, name):
    return models.CheckConstraint(condition=Q(**{f'{field}__regex': r'\S'}), name=name)


def code_constraint(name):
    return models.CheckConstraint(
        condition=Q(code__regex=r'^[a-z0-9]+(-[a-z0-9]+)*$') & ~Q(code__regex=r'\s'), name=name,
    )


def deadline_constraints(prefix):
    day, instant, zone = prefix, f'{prefix}_at', f'{prefix}_timezone'
    return [
        models.CheckConstraint(
            condition=Q(**{f'{day}__isnull': False}) | Q(**{f'{instant}__isnull': True, zone: ''}),
            name=f'comp_{prefix}_day_pair',
        ),
        models.CheckConstraint(
            condition=Q(**{f'{instant}__isnull': True}) | (
                Q(**{f'{day}__isnull': False}) & ~Q(**{zone: ''})
            ), name=f'comp_{prefix}_at_pair',
        ),
    ]


class CleanFieldsModel(models.Model):
    """字段校验前统一去除文本首尾空白；不隐式替代写入事务。"""

    class Meta:
        abstract = True

    def clean_fields(self, exclude=None):
        for field in self._meta.fields:
            value = getattr(self, field.attname)
            if field.name not in (exclude or ()) and isinstance(value, str):
                setattr(self, field.attname, value.strip())
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        errors = {}
        for field in self._meta.fields:
            value = getattr(self, field.attname)
            if isinstance(field, models.DateTimeField) and isinstance(value, datetime):
                if timezone.is_naive(value):
                    errors[field.name] = '请提供带时区的时间。'
        if errors:
            raise ValidationError(errors)


class CompetitionTaxonomy(CleanFieldsModel):
    class Kind(models.TextChoices):
        CATEGORY = 'category', '主分类'
        TAG = 'tag', '标签'

    code = models.SlugField('词条编码', max_length=64, unique=True, validators=[validate_code])
    kind = models.CharField('词条用途', max_length=20, choices=Kind.choices)
    name = models.CharField('展示名称', max_length=50)
    is_active = models.BooleanField('可供新选择', default=True)
    sort_order = models.PositiveIntegerField('展示顺序', default=0)

    class Meta:
        verbose_name = '赛事分类或标签'
        verbose_name_plural = '赛事分类与标签'
        ordering = ('sort_order', 'id')
        constraints = [
            code_constraint('comp_taxonomy_code_format'),
            nonblank_constraint('name', 'comp_taxonomy_name_notblank'),
            models.CheckConstraint(condition=Q(kind__in=['category', 'tag']), name='comp_taxonomy_kind'),
            models.UniqueConstraint(fields=['kind', 'name'], name='comp_taxonomy_kind_name_unique'),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if not self._state.adding:
            original = type(self).objects.filter(pk=self.pk).values('code', 'kind').first()
            if original:
                errors = {
                    field: '词条建立后不能更改编码或用途。'
                    for field in ('code', 'kind') if original[field] != getattr(self, field)
                }
                if errors:
                    raise ValidationError(errors)


class Competition(CleanFieldsModel):
    class Level(models.TextChoices):
        UNKNOWN = 'unknown', '未注明'
        INTERNATIONAL = 'international', '国际'
        NATIONAL = 'national', '全国'
        PROVINCIAL = 'provincial', '省级'
        MUNICIPAL = 'municipal', '市级'
        UNIVERSITY = 'university', '校级'
        COLLEGE = 'college', '院系级'
        OTHER = 'other', '其他'

    class ParticipationType(models.TextChoices):
        UNKNOWN = 'unknown', '未说明'
        INDIVIDUAL = 'individual', '个人赛'
        TEAM = 'team', '团队赛'
        BOTH = 'both', '同时允许个人与团队'

    class PublicationStatus(models.TextChoices):
        DRAFT = 'draft', '草稿'
        PUBLISHED = 'published', '已公开'
        WITHDRAWN = 'withdrawn', '已下架'

    code = models.SlugField('稳定编码', max_length=80, unique=True, validators=[validate_code])
    title = models.CharField('赛事名称', max_length=200)
    edition = models.CharField('年度或届次', max_length=80)
    summary = models.CharField('列表简介', max_length=500, blank=True, default='')
    description = models.TextField('赛事详情', blank=True, default='', validators=[MaxLengthValidator(20000)])
    category = models.ForeignKey(
        CompetitionTaxonomy, verbose_name='主分类', on_delete=models.PROTECT,
        null=True, blank=True, related_name='categorized_competitions',
        limit_choices_to={'kind': CompetitionTaxonomy.Kind.CATEGORY},
    )
    tags = models.ManyToManyField(
        CompetitionTaxonomy, verbose_name='标签', blank=True, related_name='tagged_competitions',
        limit_choices_to={'kind': CompetitionTaxonomy.Kind.TAG, 'is_active': True},
    )
    level = models.CharField('赛事范围', max_length=20, choices=Level.choices, default=Level.UNKNOWN)
    organizer = models.CharField('主办方', max_length=500, blank=True, default='')
    tracks = models.TextField('赛道说明', blank=True, default='', validators=[MaxLengthValidator(5000)])
    eligibility = models.TextField('参赛资格', blank=True, default='', validators=[MaxLengthValidator(5000)])
    participation_type = models.CharField(
        '参赛形式', max_length=20, choices=ParticipationType.choices, default=ParticipationType.UNKNOWN,
    )
    team_size_min = models.PositiveSmallIntegerField(
        '官方团队人数下限', null=True, blank=True, validators=[MinValueValidator(1)],
    )
    team_size_max = models.PositiveSmallIntegerField(
        '官方团队人数上限', null=True, blank=True, validators=[MinValueValidator(1)],
    )
    registration_method = models.TextField('官方报名方式', blank=True, default='', validators=[MaxLengthValidator(5000)])
    registration_url = models.URLField(
        '官方报名入口', max_length=2048, blank=True, default='', validators=[URLValidator(schemes=['http', 'https'])],
    )
    campus_arrangements = models.TextField('同济校内安排', blank=True, default='', validators=[MaxLengthValidator(5000)])
    registration_deadline = models.DateField('报名截止日期', null=True, blank=True)
    registration_deadline_at = models.DateTimeField('报名截止时刻', null=True, blank=True)
    registration_deadline_timezone = models.CharField(
        '报名截止来源时区', max_length=64, blank=True, default='', validators=[validate_source_timezone],
    )
    submission_deadline = models.DateField('作品提交截止日期', null=True, blank=True)
    submission_deadline_at = models.DateTimeField('作品提交截止时刻', null=True, blank=True)
    submission_deadline_timezone = models.CharField(
        '作品提交来源时区', max_length=64, blank=True, default='', validators=[validate_source_timezone],
    )
    campus_deadline = models.DateField('校内截止日期', null=True, blank=True)
    campus_deadline_at = models.DateTimeField('校内截止时刻', null=True, blank=True)
    campus_deadline_timezone = models.CharField(
        '校内截止来源时区', max_length=64, blank=True, default='', validators=[validate_source_timezone],
    )
    deadline_notes = models.TextField('截止时间说明', blank=True, default='', validators=[MaxLengthValidator(5000)])
    publication_status = models.CharField(
        '发布状态', max_length=20, choices=PublicationStatus.choices, default=PublicationStatus.DRAFT,
    )
    published_at = models.DateTimeField('首次发布时间', null=True, blank=True, editable=False)
    withdrawal_reason = models.CharField('最近下架原因', max_length=500, blank=True, default='')
    last_verified_at = models.DateTimeField('整条核验时间', null=True, blank=True, editable=False)
    created_at = models.DateTimeField('建档时间', auto_now_add=True)
    updated_at = models.DateTimeField('内容更新时间', auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='建档人', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_competitions', editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='最近修改人', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_competitions', editable=False,
    )
    recruitment_enabled = models.BooleanField('开放站内招募', default=False)
    recruitment_deadline = models.DateTimeField('平台招募截止', null=True, blank=True)
    recruitment_note = models.CharField('招募期限核验依据', max_length=1000, blank=True, default='')

    class Meta:
        verbose_name = '赛事届次'
        verbose_name_plural = '赛事届次'
        ordering = ('-published_at', '-id')
        indexes = [
            models.Index(fields=['publication_status', 'published_at', 'id'], name='comp_status_pub_idx'),
            models.Index(fields=['publication_status', 'registration_deadline', 'id'], name='comp_status_deadline_idx'),
        ]
        constraints = [
            code_constraint('competition_code_format'),
            nonblank_constraint('title', 'competition_title_notblank'),
            nonblank_constraint('edition', 'competition_edition_notblank'),
            models.CheckConstraint(condition=Q(level__in=[
                'unknown', 'international', 'national', 'provincial', 'municipal',
                'university', 'college', 'other',
            ]), name='comp_level_valid'),
            models.CheckConstraint(condition=Q(participation_type__in=[
                'unknown', 'individual', 'team', 'both',
            ]), name='comp_participation_valid'),
            models.CheckConstraint(condition=Q(publication_status__in=[
                'draft', 'published', 'withdrawn',
            ]), name='comp_status_valid'),
            models.CheckConstraint(
                condition=Q(team_size_min__isnull=True) | Q(team_size_min__gte=1), name='comp_team_min_positive',
            ),
            models.CheckConstraint(
                condition=Q(team_size_max__isnull=True) | Q(team_size_max__gte=1), name='comp_team_max_positive',
            ),
            models.CheckConstraint(
                condition=Q(team_size_min__isnull=True) | Q(team_size_max__isnull=True)
                | Q(team_size_min__lte=F('team_size_max')), name='comp_team_size_order',
            ),
            models.CheckConstraint(
                condition=~Q(participation_type='individual') | Q(
                    team_size_min__isnull=True, team_size_max__isnull=True, recruitment_enabled=False,
                ), name='comp_individual_without_team',
            ),
            models.CheckConstraint(
                condition=Q(publication_status='draft', published_at__isnull=True)
                | Q(publication_status__in=['published', 'withdrawn'], published_at__isnull=False),
                name='comp_status_publication_time',
            ),
            models.CheckConstraint(
                condition=~Q(publication_status='published') | Q(
                    summary__regex=r'\S', description__regex=r'\S', category__isnull=False, last_verified_at__isnull=False,
                ), name='comp_published_fields_present',
            ),
            models.CheckConstraint(
                condition=~Q(publication_status='withdrawn') | Q(withdrawal_reason__regex=r'\S'),
                name='comp_withdrawal_reason_present',
            ),
            models.CheckConstraint(
                condition=Q(recruitment_enabled=False) | Q(
                    publication_status='published', participation_type__in=['team', 'both'],
                    recruitment_deadline__isnull=False, recruitment_note__regex=r'\S',
                ), name='comp_recruitment_requirements',
            ),
            *deadline_constraints('registration_deadline'),
            *deadline_constraints('submission_deadline'),
            *deadline_constraints('campus_deadline'),
        ]

    def __str__(self):
        return self.title

    @property
    def is_recruitment_open(self):
        """只计算赛事侧条件；不代替账号、队伍、卡片的权限判断。"""
        return bool(
            self.publication_status == self.PublicationStatus.PUBLISHED
            and self.participation_type in (self.ParticipationType.TEAM, self.ParticipationType.BOTH)
            and self.recruitment_enabled and self.recruitment_deadline
            and self.recruitment_deadline > timezone.now()
        )

    def clean(self):
        super().clean()
        errors = {}
        previous = None if self._state.adding else type(self).objects.filter(pk=self.pk).first()
        if previous:
            if self.code != previous.code:
                errors['code'] = '赛事编码建立后不能修改。'
            if previous.published_at is not None and self.published_at != previous.published_at:
                errors['published_at'] = '首次发布时间不能重置。'

        for prefix in ('registration_deadline', 'submission_deadline', 'campus_deadline'):
            day, instant, zone_name = (
                getattr(self, prefix), getattr(self, f'{prefix}_at'), getattr(self, f'{prefix}_timezone'),
            )
            zone = None
            if zone_name:
                try:
                    zone = parse_source_timezone(zone_name)
                except ValidationError as exc:
                    errors[f'{prefix}_timezone'] = exc.messages
            if day is None and (instant is not None or zone_name):
                errors[prefix] = '填写精确时刻或时区时必须提供对应日期。'
            if isinstance(instant, datetime):
                if not zone_name:
                    errors[f'{prefix}_timezone'] = '精确时刻必须有来源时区。'
                elif zone and timezone.is_aware(instant) and isinstance(day, date):
                    if instant.astimezone(zone).date() != day:
                        errors[f'{prefix}_at'] = '精确时刻在来源时区的日期与截止日期不一致。'

        category = None
        if self.category_id:
            category = CompetitionTaxonomy.objects.filter(pk=self.category_id).first()
            if category and category.kind != CompetitionTaxonomy.Kind.CATEGORY:
                errors['category'] = '主分类必须使用分类词条。'
            if category and not category.is_active and (not previous or previous.category_id != self.category_id):
                errors['category'] = '不能新增选择停用分类。'

        if self.publication_status == self.PublicationStatus.PUBLISHED:
            for field in ('summary', 'description', 'published_at', 'last_verified_at'):
                if not getattr(self, field):
                    errors[field] = '发布前必须填写或完成核验。'
            if category is None:
                errors['category'] = '发布前必须选择主分类。'
            elif (not previous or previous.publication_status != self.PublicationStatus.PUBLISHED) and not category.is_active:
                errors['category'] = '发布前必须选择启用的主分类。'
            if self._state.adding or self.sources.filter(is_primary=True).count() != 1:
                errors['__all__'] = '请先保存草稿，再设置恰好一个已核验主来源后发布。'
            elif self.sources.filter(last_verified_at__isnull=True).exists():
                errors['__all__'] = '公开来源必须全部经过核验。'
            elif self.campus_arrangements and not self.sources.filter(source_type='campus').exists():
                errors['campus_arrangements'] = '校内安排必须有校内官方来源。'

        enabling = self.recruitment_enabled and (
            not previous or not previous.recruitment_enabled
            or previous.recruitment_deadline != self.recruitment_deadline
        )
        if enabling and isinstance(self.recruitment_deadline, datetime):
            if timezone.is_aware(self.recruitment_deadline) and self.recruitment_deadline <= timezone.now():
                errors['recruitment_deadline'] = '启用或修改招募期限时必须选择未来时刻。'
        if errors:
            raise ValidationError(errors)


class CompetitionSource(CleanFieldsModel):
    class SourceType(models.TextChoices):
        OFFICIAL = 'official', '赛事官方'
        CAMPUS = 'campus', '校内官方'

    competition = models.ForeignKey(
        Competition, verbose_name='赛事届次', on_delete=models.CASCADE, related_name='sources',
    )
    source_type = models.CharField('来源类型', max_length=20, choices=SourceType.choices)
    source_name = models.CharField('来源名称', max_length=200)
    source_url = models.URLField(
        '原文链接', max_length=2048, validators=[URLValidator(schemes=['http', 'https'])],
    )
    is_primary = models.BooleanField('主来源', default=False)
    source_published_on = models.DateField('原通知发布日期', null=True, blank=True)
    source_updated_on = models.DateField('原通知更新日期', null=True, blank=True)
    fetched_at = models.DateTimeField('最近成功采集时间', null=True, blank=True, editable=False)
    last_verified_at = models.DateTimeField('来源核验时间', null=True, blank=True, editable=False)

    class Meta:
        verbose_name = '赛事来源'
        verbose_name_plural = '赛事来源'
        ordering = ('-is_primary', 'id')
        constraints = [
            models.UniqueConstraint(fields=['competition'], condition=Q(is_primary=True), name='comp_one_primary_source'),
            nonblank_constraint('source_name', 'comp_source_name_notblank'),
            models.CheckConstraint(condition=Q(source_type__in=['official', 'campus']), name='comp_source_type_valid'),
            models.CheckConstraint(condition=Q(source_url__regex=r'^https?://'), name='comp_source_http_url'),
        ]

    def __str__(self):
        return self.source_name

    def clean(self):
        super().clean()
        if self.competition_id and Competition.objects.filter(
            pk=self.competition_id, publication_status=Competition.PublicationStatus.PUBLISHED,
        ).exists() and self.last_verified_at is None:
            raise ValidationError({'last_verified_at': '公开赛事的来源必须经过核验。'})
