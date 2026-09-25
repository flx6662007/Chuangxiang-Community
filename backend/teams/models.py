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

class RecruitmentOption(DomainModel):
    """角色、技能或校区的受控词条。"""
    immutable_fields = ('code', 'kind', 'name')
    code = models.SlugField('稳定编码', max_length=64, unique=True)
    kind = models.CharField('用途', max_length=12, choices=[('role', 'role'), ('skill', 'skill'), ('campus', 'campus')])
    name = models.CharField('名称', max_length=80)
    is_active = models.BooleanField('可供新选择', default=True)
    sort_order = models.PositiveIntegerField('顺序', default=0)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'RecruitmentOption'
        constraints = [
            models.UniqueConstraint(fields=['kind', 'name'], name='recruitmentoption_kind_name'),
            models.CheckConstraint(condition=Q(code__regex=r'\S'), name='t01_code_nonblank'),
            models.CheckConstraint(condition=Q(kind__in=['role', 'skill', 'campus']), name='t01_kind_enum'),
            models.CheckConstraint(condition=Q(kind__regex=r'\S'), name='t01_kind_nonblank'),
            models.CheckConstraint(condition=Q(name__regex=r'\S'), name='t01_name_nonblank'),
        ]
        indexes = [
            models.Index(fields=['kind', 'is_active', 'sort_order'], name='t01_idx_1'),
        ]


class Team(DomainModel):
    """同一具体赛事届次下持续存在的队伍；换卡不换队伍。"""
    immutable_fields = ('code', 'competition_id', 'recruiter_id', 'created_at')
    code = models.SlugField('稳定队伍编号', max_length=80, unique=True, default=new_code('team'))
    competition = models.ForeignKey('competitions.Competition', verbose_name='所属赛事届次', on_delete=models.PROTECT, related_name='+')
    recruiter = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='招募者', on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField('创建时间', default=timezone.now)
    dissolved_at = models.DateTimeField('实际解散时间', null=True, blank=True)

    def active_members(self):
        return Membership.objects.filter(team_id=self.pk, ended_at__isnull=True)

    @property
    def is_dissolution_pending(self):
        return DissolutionRequest.objects.filter(team_id=self.pk, status='pending').exists()

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'Team'
        constraints = [
            models.CheckConstraint(condition=Q(dissolved_at__isnull=True) | Q(dissolved_at__gte=F('created_at')), name='team_end_order'),
        ]
        indexes = [
            models.Index(fields=['competition', 'dissolved_at'], name='t02_idx_1'),
            models.Index(fields=['recruiter', 'created_at'], name='t02_idx_2'),
        ]


class Recruitment(DomainModel):
    """一轮招募的身份、期限与生命周期；可编辑内容放入不可变版本。"""
    immutable_fields = ('code', 'team_id', 'created_at')
    code = models.SlugField('卡片编号', max_length=80, unique=True, default=new_code('recruitment'))
    team = models.ForeignKey('teams.Team', verbose_name='所属队伍', on_delete=models.PROTECT, related_name='+')
    current_revision = models.ForeignKey('teams.RecruitmentRevision', verbose_name='当前内容版本', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    publication_status = models.CharField('可见状态', max_length=12, choices=[('draft', 'draft'), ('published', 'published'), ('withdrawn', 'withdrawn')], default='draft')
    duration_days = models.PositiveSmallIntegerField('选择的有效天数')
    created_at = models.DateTimeField('建档时间', default=timezone.now)
    published_at = models.DateTimeField('首次发布时间', null=True, blank=True)
    expires_at = models.DateTimeField('本卡到期时刻', null=True, blank=True)
    last_edited_at = models.DateTimeField('最后实际编辑时间', null=True, blank=True)
    closed_at = models.DateTimeField('招募结束时间', null=True, blank=True)
    close_reason = models.CharField('结束原因', max_length=32, choices=[('', '未填写'), ('manual', 'manual'), ('expired', 'expired'), ('competition_stopped', 'competition_stopped'), ('competition_withdrawn', 'competition_withdrawn'), ('team_dissolved', 'team_dissolved')], default='', blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='关闭操作者', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    withdrawn_at = models.DateTimeField('最近下架时间', null=True, blank=True)
    withdrawal_reason = models.CharField('下架原因', max_length=500, default='', blank=True)

    @property
    def joined_member_count(self):
        return Membership.objects.filter(application__recruitment_id=self.pk, ended_at__isnull=True).count()

    @property
    def current_existing_member_count(self):
        if not self.current_revision_id:
            return 0
        departed = RecruitmentBaselineMember.objects.filter(revision_id=self.current_revision_id, membership__ended_at__isnull=False).count()
        return self.current_revision.existing_member_count - departed

    @property
    def remaining_slots(self):
        return max(0, self.current_revision.recruitment_quota - self.joined_member_count) if self.current_revision_id else 0

    @property
    def is_open(self):
        return bool(self.publication_status == 'published' and self.closed_at is None
                    and self.expires_at and self.expires_at > timezone.now()
                    and self.team.dissolved_at is None and not self.team.is_dissolution_pending
                    and self.team.competition.is_recruitment_open and self.remaining_slots > 0)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'Recruitment'
        constraints = [
            models.UniqueConstraint(fields=['team'], name='recruitment_one_open', condition=Q(publication_status='published', closed_at__isnull=True)),
            models.CheckConstraint(condition=Q(duration_days__in=[3, 7, 14]), name='recruitment_duration'),
            models.CheckConstraint(condition=Q(publication_status='draft', published_at__isnull=True) | Q(publication_status__in=['published', 'withdrawn'], published_at__isnull=False, expires_at__isnull=False, current_revision__isnull=False), name='recruitment_published'),
            models.CheckConstraint(condition=Q(expires_at__isnull=True) | Q(published_at__isnull=False, expires_at__gt=F('published_at')), name='recruitment_expiry'),
            models.CheckConstraint(condition=Q(closed_at__isnull=True, close_reason='') | (Q(closed_at__isnull=False) & ~Q(close_reason='')), name='recruitment_close_pair'),
            models.CheckConstraint(condition=~Q(publication_status='withdrawn') | Q(withdrawn_at__isnull=False, withdrawal_reason__regex=r'\S'), name='recruitment_withdrawn'),
            models.CheckConstraint(condition=Q(publication_status__in=['draft', 'published', 'withdrawn']), name='t03_publication_status_enum'),
            models.CheckConstraint(condition=Q(close_reason__in=['', 'manual', 'expired', 'competition_stopped', 'competition_withdrawn', 'team_dissolved']), name='t03_close_reason_enum'),
        ]
        indexes = [
            models.Index(fields=['team', 'created_at'], name='t03_idx_1'),
            models.Index(fields=['publication_status', 'closed_at', 'expires_at'], name='t03_idx_2'),
        ]


class RecruitmentRevision(DomainModel):
    """某张卡的一次完整内容版本；版本创建后不可修改。"""
    immutable_fields = '*'
    recruitment = models.ForeignKey('teams.Recruitment', verbose_name='所属卡片', on_delete=models.PROTECT, related_name='+')
    version = models.PositiveIntegerField('版本序号', validators=[MinValueValidator(1)])
    existing_member_count = models.PositiveIntegerField('申报已有成员数', validators=[MinValueValidator(1)])
    recruitment_quota = models.PositiveIntegerField('本轮计划招募人数')
    foundation_requirement = models.CharField('基础要求', max_length=24, choices=[('beginner_ok', 'beginner_ok'), ('introductory', 'introductory'), ('project_experience', 'project_experience')])
    weekly_effort = models.CharField('每周投入档位', max_length=16, choices=[('up_to_2', 'up_to_2'), ('over_2_to_5', 'over_2_to_5'), ('over_5_to_10', 'over_5_to_10'), ('over_10', 'over_10')])
    collaboration_goal = models.CharField('合作目标', max_length=24, choices=[('', '未填写'), ('learning', 'learning'), ('deliver_entry', 'deliver_entry'), ('strong_result', 'strong_result')], default='', blank=True)
    expected_duration = models.CharField('入队后合作时长', max_length=24, choices=[('', '未填写'), ('up_to_1_month', 'up_to_1_month'), ('over_1_to_3_months', 'over_1_to_3_months'), ('over_3_to_6_months', 'over_3_to_6_months'), ('over_6_months', 'over_6_months')], default='', blank=True)
    collaboration_mode = models.CharField('协作方式', max_length=12, choices=[('online', 'online'), ('offline', 'offline'), ('hybrid', 'hybrid')])
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='本次编辑人', on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField('本版本生效时间', default=timezone.now)
    current_skills = models.ManyToManyField('teams.RecruitmentOption', through='teams.RecruitmentCurrentSkill', blank=True, related_name='+')
    required_roles = models.ManyToManyField('teams.RecruitmentOption', through='teams.RecruitmentRequiredRole', blank=True, related_name='+')
    required_skills = models.ManyToManyField('teams.RecruitmentOption', through='teams.RecruitmentRequiredSkill', blank=True, related_name='+')
    campuses = models.ManyToManyField('teams.RecruitmentOption', through='teams.RecruitmentCampus', blank=True, related_name='+')

    def validate_ready(self):
        """装配完多选和基数后、切换主表版本前，在事务中调用。"""
        from common.models import require
        from .validation import validate_capacity
        self.full_clean()
        validate_capacity(self)
        require(bool(self.pk), '版本须先保存再装配关联。')
        require(self.campuses.exists() == (self.collaboration_mode != 'online'), '线下/混合须选校区，线上不存校区。')
        expected = set(self.recruitment.team.active_members().exclude(application__recruitment_id=self.recruitment_id).values_list('pk', flat=True))
        recorded = set(RecruitmentBaselineMember.objects.filter(revision=self, membership__ended_at__isnull=True).values_list('membership_id', flat=True))
        require(recorded == expected, '版本必须记录完整且不重复的有效平台基数成员。')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'RecruitmentRevision'
        constraints = [
            models.UniqueConstraint(fields=['recruitment', 'version'], name='recruitmentrevisi_version'),
            models.CheckConstraint(condition=Q(existing_member_count__gte=1), name='recruitmentrevisi_baseline'),
            models.CheckConstraint(condition=Q(version__gte=1), name='t04_version_positive'),
            models.CheckConstraint(condition=Q(existing_member_count__gte=1), name='t04_existing_member_count_positive'),
            models.CheckConstraint(condition=Q(foundation_requirement__in=['beginner_ok', 'introductory', 'project_experience']), name='t04_foundation_requirem_enum'),
            models.CheckConstraint(condition=Q(foundation_requirement__regex=r'\S'), name='t04_foundation_requirem_nonblank'),
            models.CheckConstraint(condition=Q(weekly_effort__in=['up_to_2', 'over_2_to_5', 'over_5_to_10', 'over_10']), name='t04_weekly_effort_enum'),
            models.CheckConstraint(condition=Q(weekly_effort__regex=r'\S'), name='t04_weekly_effort_nonblank'),
            models.CheckConstraint(condition=Q(collaboration_goal__in=['', 'learning', 'deliver_entry', 'strong_result']), name='t04_collaboration_goal_enum'),
            models.CheckConstraint(condition=Q(expected_duration__in=['', 'up_to_1_month', 'over_1_to_3_months', 'over_3_to_6_months', 'over_6_months']), name='t04_expected_duration_enum'),
            models.CheckConstraint(condition=Q(collaboration_mode__in=['online', 'offline', 'hybrid']), name='t04_collaboration_mode_enum'),
            models.CheckConstraint(condition=Q(collaboration_mode__regex=r'\S'), name='t04_collaboration_mode_nonblank'),
        ]
        indexes = [
        ]


class RecruitmentBaselineMember(DomainModel):
    """本版本申报已有成员数中，已被平台识别的正式成员；线下成员不逐人建档。"""
    immutable_fields = '*'
    revision = models.ForeignKey('teams.RecruitmentRevision', verbose_name='人数申报版本', on_delete=models.PROTECT, related_name='+')
    membership = models.ForeignKey('teams.Membership', verbose_name='计入基数的成员关系', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'RecruitmentBaselineMember'
        constraints = [
            models.UniqueConstraint(fields=['revision', 'membership'], name='recruitmentbaseli_pair'),
        ]
        indexes = [
            models.Index(fields=['membership', 'revision'], name='t05_idx_1'),
        ]


class Application(DomainModel):
    """一人对一张卡唯一的一次申请；终结后不复用。"""
    immutable_fields = ('recruitment_id', 'applicant_id', 'submitted_at')
    recruitment = models.ForeignKey('teams.Recruitment', verbose_name='目标卡片', on_delete=models.PROTECT, related_name='+')
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='申请人', on_delete=models.PROTECT, related_name='+')
    current_revision = models.ForeignKey('teams.ApplicationRevision', verbose_name='当前申请资料版本', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    status = models.CharField('处理阶段', max_length=20, choices=[('pending', 'pending'), ('contact_open', 'contact_open'), ('joined', 'joined'), ('withdrawn', 'withdrawn'), ('rejected', 'rejected'), ('ended', 'ended')], default='pending')
    submitted_at = models.DateTimeField('提交时间', default=timezone.now)
    contact_opened_at = models.DateTimeField('接受并开放联系方式时间', null=True, blank=True)
    applicant_confirmed_at = models.DateTimeField('申请人当前正式确认时间', null=True, blank=True)
    applicant_confirmed_revision = models.ForeignKey('teams.ApplicationRevision', verbose_name='申请人确认的申请版本', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    recruiter_confirmed_at = models.DateTimeField('招募者当前正式确认时间', null=True, blank=True)
    recruiter_confirmed_revision = models.ForeignKey('teams.ApplicationRevision', verbose_name='招募者确认的申请版本', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    resolved_at = models.DateTimeField('申请终结时间', null=True, blank=True)
    end_reason = models.CharField('结束原因', max_length=32, choices=[('', '未填写'), ('joined', 'joined'), ('withdrawn', 'withdrawn'), ('rejected', 'rejected'), ('recruiter_terminated', 'recruiter_terminated'), ('full', 'full'), ('expired', 'expired'), ('card_closed', 'card_closed'), ('card_withdrawn', 'card_withdrawn'), ('competition_stopped', 'competition_stopped'), ('competition_withdrawn', 'competition_withdrawn'), ('joined_other_team', 'joined_other_team'), ('team_dissolved', 'team_dissolved'), ('account_disabled', 'account_disabled')], default='', blank=True)

    @property
    def is_paused(self):
        if self.status not in ['pending', 'contact_open']:
            return False
        return bool(not self.current_revision_id
                    or self.current_revision.recruitment_revision_id != self.recruitment.current_revision_id
                    or self.recruitment.team.is_dissolution_pending)

    def can_view_contact(self, viewer_id):
        """仅返回权限判定；实际联系方式由受权接口读取 User 最新资料。"""
        if viewer_id not in [self.applicant_id, self.recruitment.team.recruiter_id] or not self.contact_opened_at:
            return False
        if self.recruitment.team.dissolved_at is not None:
            return False
        if self.status in ['pending', 'contact_open']:
            card = self.recruitment
            return bool(card.publication_status == 'published' and card.closed_at is None
                        and card.expires_at and card.expires_at > timezone.now()
                        and card.team.competition.is_recruitment_open)
        return self.status == 'joined' and Membership.objects.filter(application_id=self.pk, ended_at__isnull=True).exists()

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'Application'
        constraints = [
            models.UniqueConstraint(fields=['recruitment', 'applicant'], name='application_once'),
            models.CheckConstraint(condition=Q(applicant_confirmed_at__isnull=True, applicant_confirmed_revision__isnull=True) | Q(applicant_confirmed_at__isnull=False, applicant_confirmed_revision__isnull=False), name='application_applicant_pair'),
            models.CheckConstraint(condition=Q(recruiter_confirmed_at__isnull=True, recruiter_confirmed_revision__isnull=True) | Q(recruiter_confirmed_at__isnull=False, recruiter_confirmed_revision__isnull=False), name='application_recruiter_pair'),
            models.CheckConstraint(condition=Q(status__in=['pending','contact_open'], resolved_at__isnull=True, end_reason='') | Q(status='joined', resolved_at__isnull=False, end_reason='joined') | Q(status='withdrawn', resolved_at__isnull=False, end_reason='withdrawn') | Q(status='rejected', resolved_at__isnull=False, end_reason='rejected') | (Q(status='ended', resolved_at__isnull=False) & ~Q(end_reason__in=['','joined','withdrawn','rejected'])), name='application_result'),
            models.CheckConstraint(condition=~Q(status__in=['contact_open','joined']) | Q(contact_opened_at__isnull=False), name='application_contact'),
            models.CheckConstraint(condition=~Q(status='joined') | Q(current_revision__isnull=False, applicant_confirmed_at__isnull=False, recruiter_confirmed_at__isnull=False, applicant_confirmed_revision=F('current_revision'), recruiter_confirmed_revision=F('current_revision')), name='application_joined_confirm'),
            models.CheckConstraint(condition=Q(status__in=['pending', 'contact_open', 'joined', 'withdrawn', 'rejected', 'ended']), name='t06_status_enum'),
            models.CheckConstraint(condition=Q(end_reason__in=['', 'joined', 'withdrawn', 'rejected', 'recruiter_terminated', 'full', 'expired', 'card_closed', 'card_withdrawn', 'competition_stopped', 'competition_withdrawn', 'joined_other_team', 'team_dissolved', 'account_disabled']), name='t06_end_reason_enum'),
        ]
        indexes = [
            models.Index(fields=['applicant', 'status', 'submitted_at'], name='t06_idx_1'),
            models.Index(fields=['recruitment', 'status'], name='t06_idx_2'),
        ]


class ApplicationRevision(DomainModel):
    """初次提交或卡片更新后继续申请时的资料版本与条件接受记录。"""
    immutable_fields = '*'
    application = models.ForeignKey('teams.Application', verbose_name='所属申请', on_delete=models.PROTECT, related_name='+')
    version = models.PositiveIntegerField('资料版本号', validators=[MinValueValidator(1)])
    recruitment_revision = models.ForeignKey('teams.RecruitmentRevision', verbose_name='已接受的卡片版本', on_delete=models.PROTECT, related_name='+')
    weekly_effort = models.CharField('每周可投入时间', max_length=16, choices=[('up_to_2', 'up_to_2'), ('over_2_to_5', 'over_2_to_5'), ('over_5_to_10', 'over_5_to_10'), ('over_10', 'over_10')])
    accepted_at = models.DateTimeField('申请人接受该版条件的时间', default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='提交或继续的申请人', on_delete=models.PROTECT, related_name='+')
    desired_roles = models.ManyToManyField('teams.RecruitmentOption', through='teams.ApplicationDesiredRole', blank=True, related_name='+')
    skills = models.ManyToManyField('teams.RecruitmentOption', through='teams.ApplicationSkill', blank=True, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'ApplicationRevision'
        constraints = [
            models.UniqueConstraint(fields=['application', 'version'], name='applicationrevisi_version'),
            models.CheckConstraint(condition=Q(version__gte=1), name='t07_version_positive'),
            models.CheckConstraint(condition=Q(weekly_effort__in=['up_to_2', 'over_2_to_5', 'over_5_to_10', 'over_10']), name='t07_weekly_effort_enum'),
            models.CheckConstraint(condition=Q(weekly_effort__regex=r'\S'), name='t07_weekly_effort_nonblank'),
        ]
        indexes = [
        ]


class Membership(DomainModel):
    """用户在队伍中的一段正式成员关系；结束只填结束信息，不删除。"""
    immutable_fields = ('team_id', 'competition_id', 'user_id', 'join_source', 'application_id', 'joined_at')
    team = models.ForeignKey('teams.Team', verbose_name='队伍', on_delete=models.PROTECT, related_name='+')
    competition = models.ForeignKey('competitions.Competition', verbose_name='所属赛事届次', on_delete=models.PROTECT, related_name='+')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='成员账号', on_delete=models.PROTECT, related_name='+')
    join_source = models.CharField('加入来源', max_length=16, choices=[('recruiter', 'recruiter'), ('application', 'application')])
    application = models.OneToOneField('teams.Application', verbose_name='成功申请', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    joined_at = models.DateTimeField('正式加入时间', default=timezone.now)
    ended_at = models.DateTimeField('成员关系结束时间', null=True, blank=True)
    end_reason = models.CharField('结束方式', max_length=20, choices=[('', '未填写'), ('exit', 'exit'), ('removal', 'removal'), ('dissolution', 'dissolution')], default='', blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'Membership'
        constraints = [
            models.UniqueConstraint(fields=['user', 'competition'], name='membership_one_active', condition=Q(ended_at__isnull=True)),
            models.CheckConstraint(condition=Q(join_source='recruiter', application__isnull=True) | Q(join_source='application', application__isnull=False), name='membership_source'),
            models.CheckConstraint(condition=Q(ended_at__isnull=True, end_reason='') | (Q(ended_at__isnull=False, ended_at__gte=F('joined_at')) & ~Q(end_reason='')), name='membership_end_pair'),
            models.CheckConstraint(condition=Q(join_source__in=['recruiter', 'application']), name='t08_join_source_enum'),
            models.CheckConstraint(condition=Q(join_source__regex=r'\S'), name='t08_join_source_nonblank'),
            models.CheckConstraint(condition=Q(end_reason__in=['', 'exit', 'removal', 'dissolution']), name='t08_end_reason_enum'),
        ]
        indexes = [
            models.Index(fields=['team', 'ended_at'], name='t08_idx_1'),
        ]


class DepartureRequest(DomainModel):
    """成员退出与招募者移除共用请求表，保留两个业务名称。"""
    membership = models.ForeignKey('teams.Membership', verbose_name='目标成员关系', on_delete=models.PROTECT, related_name='+')
    kind = models.CharField('请求类型', max_length=12, choices=[('exit', 'exit'), ('removal', 'removal')])
    initiator = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='发起人', on_delete=models.PROTECT, related_name='+')
    responder = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='应回应人', on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField('发起时间', default=timezone.now)
    deadline_at = models.DateTimeField('回应截止')
    status = models.CharField('请求结果', max_length=24, choices=[('pending', 'pending'), ('approved', 'approved'), ('rejected', 'rejected'), ('withdrawn', 'withdrawn'), ('timed_out', 'timed_out'), ('team_dissolved', 'team_dissolved')], default='pending')
    response = models.CharField('实际回应', max_length=12, choices=[('', '未填写'), ('agree', 'agree'), ('reject', 'reject')], default='', blank=True)
    responded_at = models.DateTimeField('实际回应时间', null=True, blank=True)
    resolved_at = models.DateTimeField('请求结束时间', null=True, blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'DepartureRequest'
        constraints = [
            models.UniqueConstraint(fields=['membership'], name='departurerequest_one_pending', condition=Q(status='pending')),
            models.CheckConstraint(condition=~Q(initiator=F('responder')), name='departurerequest_two_parties'),
            models.CheckConstraint(condition=Q(status='pending', response='', responded_at__isnull=True, resolved_at__isnull=True) | Q(status='approved', response='agree', responded_at__isnull=False, resolved_at__isnull=False) | Q(status='rejected', response='reject', responded_at__isnull=False, resolved_at__isnull=False) | Q(status__in=['withdrawn','timed_out','team_dissolved'], response='', responded_at__isnull=True, resolved_at__isnull=False), name='departurerequest_outcome'),
            models.CheckConstraint(condition=Q(deadline_at=F('created_at') + timedelta(hours=24)), name='departurerequest_deadline'),
            models.CheckConstraint(condition=Q(resolved_at__isnull=True) | Q(resolved_at__gte=F('created_at')), name='departurerequest_end_order'),
            models.CheckConstraint(condition=Q(kind__in=['exit', 'removal']), name='t09_kind_enum'),
            models.CheckConstraint(condition=Q(kind__regex=r'\S'), name='t09_kind_nonblank'),
            models.CheckConstraint(condition=Q(status__in=['pending', 'approved', 'rejected', 'withdrawn', 'timed_out', 'team_dissolved']), name='t09_status_enum'),
            models.CheckConstraint(condition=Q(response__in=['', 'agree', 'reject']), name='t09_response_enum'),
        ]
        indexes = [
            models.Index(fields=['status', 'deadline_at'], name='t09_idx_1'),
            models.Index(fields=['responder', 'status'], name='t09_idx_2'),
            models.Index(fields=['membership', 'created_at'], name='t09_idx_3'),
        ]


class DissolutionRequest(DomainModel):
    """招募者发起的一次整队解散请求。"""
    team = models.ForeignKey('teams.Team', verbose_name='目标队伍', on_delete=models.PROTECT, related_name='+')
    initiator = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='发起招募者', on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField('发起时间', default=timezone.now)
    deadline_at = models.DateTimeField('回应截止')
    status = models.CharField('结果', max_length=16, choices=[('pending', 'pending'), ('completed', 'completed'), ('rejected', 'rejected'), ('withdrawn', 'withdrawn')], default='pending')
    completion_reason = models.CharField('完成方式', max_length=24, choices=[('', '未填写'), ('all_agreed', 'all_agreed'), ('timeout', 'timeout'), ('no_other_members', 'no_other_members')], default='', blank=True)
    resolved_at = models.DateTimeField('请求结束时间', null=True, blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'DissolutionRequest'
        constraints = [
            models.UniqueConstraint(fields=['team'], name='dissolutionreques_one_pending', condition=Q(status='pending')),
            models.CheckConstraint(condition=Q(status='pending', resolved_at__isnull=True, completion_reason='') | Q(status__in=['rejected','withdrawn'], resolved_at__isnull=False, completion_reason='') | (Q(status='completed', resolved_at__isnull=False) & ~Q(completion_reason='')), name='dissolutionreques_outcome'),
            models.CheckConstraint(condition=Q(deadline_at=F('created_at') + timedelta(hours=24)), name='dissolutionreques_deadline'),
            models.CheckConstraint(condition=Q(resolved_at__isnull=True) | Q(resolved_at__gte=F('created_at')), name='dissolutionreques_end_order'),
            models.CheckConstraint(condition=Q(status__in=['pending', 'completed', 'rejected', 'withdrawn']), name='t10_status_enum'),
            models.CheckConstraint(condition=Q(completion_reason__in=['', 'all_agreed', 'timeout', 'no_other_members']), name='t10_completion_reason_enum'),
        ]
        indexes = [
            models.Index(fields=['status', 'deadline_at'], name='t10_idx_1'),
            models.Index(fields=['team', 'created_at'], name='t10_idx_2'),
        ]


class DissolutionResponse(DomainModel):
    """解散发起时需回应的其他平台成员；未注册成员不生成记录。"""
    request = models.ForeignKey('teams.DissolutionRequest', verbose_name='解散请求', on_delete=models.PROTECT, related_name='+')
    membership = models.ForeignKey('teams.Membership', verbose_name='当时有效成员', on_delete=models.PROTECT, related_name='+')
    response = models.CharField('实际回应', max_length=12, choices=[('', '未填写'), ('agree', 'agree'), ('reject', 'reject')], default='', blank=True)
    responded_at = models.DateTimeField('回应时间', null=True, blank=True)
    excluded_at = models.DateTimeField('因个人退出不再需回应的时间', null=True, blank=True)

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        verbose_name = 'DissolutionResponse'
        constraints = [
            models.UniqueConstraint(fields=['request', 'membership'], name='dissolutionrespon_pair'),
            models.CheckConstraint(condition=Q(response='', responded_at__isnull=True) | Q(response__in=['agree','reject'], responded_at__isnull=False), name='dissolutionrespon_response'),
            models.CheckConstraint(condition=Q(response__in=['', 'agree', 'reject']), name='t11_response_enum'),
        ]
        indexes = [
            models.Index(fields=['request', 'response'], name='t11_idx_1'),
            models.Index(fields=['membership', 'request'], name='t11_idx_2'),
        ]


class RecruitmentCurrentSkill(DomainModel):
    """teams.RecruitmentRevision.current_skills 的显式关联。"""
    immutable_fields = '*'
    relation_owner = 'revision'
    relation_target = 'option'
    relation_kind = 'skill'
    revision = models.ForeignKey('teams.RecruitmentRevision', on_delete=models.CASCADE, related_name='+')
    option = models.ForeignKey('teams.RecruitmentOption', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision', 'option'], name='j01_unique_pair')]


class RecruitmentRequiredRole(DomainModel):
    """teams.RecruitmentRevision.required_roles 的显式关联。"""
    immutable_fields = '*'
    relation_owner = 'revision'
    relation_target = 'option'
    relation_kind = 'role'
    revision = models.ForeignKey('teams.RecruitmentRevision', on_delete=models.CASCADE, related_name='+')
    option = models.ForeignKey('teams.RecruitmentOption', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision', 'option'], name='j02_unique_pair')]


class RecruitmentRequiredSkill(DomainModel):
    """teams.RecruitmentRevision.required_skills 的显式关联。"""
    immutable_fields = '*'
    relation_owner = 'revision'
    relation_target = 'option'
    relation_kind = 'skill'
    revision = models.ForeignKey('teams.RecruitmentRevision', on_delete=models.CASCADE, related_name='+')
    option = models.ForeignKey('teams.RecruitmentOption', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision', 'option'], name='j03_unique_pair')]


class RecruitmentCampus(DomainModel):
    """teams.RecruitmentRevision.campuses 的显式关联。"""
    immutable_fields = '*'
    relation_owner = 'revision'
    relation_target = 'option'
    relation_kind = 'campus'
    revision = models.ForeignKey('teams.RecruitmentRevision', on_delete=models.CASCADE, related_name='+')
    option = models.ForeignKey('teams.RecruitmentOption', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision', 'option'], name='j04_unique_pair')]


class ApplicationDesiredRole(DomainModel):
    """teams.ApplicationRevision.desired_roles 的显式关联。"""
    immutable_fields = '*'
    relation_owner = 'revision'
    relation_target = 'option'
    relation_kind = 'role'
    revision = models.ForeignKey('teams.ApplicationRevision', on_delete=models.CASCADE, related_name='+')
    option = models.ForeignKey('teams.RecruitmentOption', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision', 'option'], name='j05_unique_pair')]


class ApplicationSkill(DomainModel):
    """teams.ApplicationRevision.skills 的显式关联。"""
    immutable_fields = '*'
    relation_owner = 'revision'
    relation_target = 'option'
    relation_kind = 'skill'
    revision = models.ForeignKey('teams.ApplicationRevision', on_delete=models.CASCADE, related_name='+')
    option = models.ForeignKey('teams.RecruitmentOption', on_delete=models.PROTECT, related_name='+')

    def clean(self):
        try:
            super().clean()
            validate_model(self)
        except ObjectDoesNotExist as exc:
            raise ValidationError('关联对象缺失或不存在。') from exc

    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision', 'option'], name='j06_unique_pair')]
