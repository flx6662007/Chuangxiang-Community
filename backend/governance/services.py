"""实名会话提交、本人可见、独立复核；举报和申诉结论不直接改变业务状态。"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import UserRestriction
from competitions.models import Competition
from teams.errors import check
from teams.models import Application, Membership, Recruitment, Team
from .models import AdminAction, Appeal, Report


EFFECT_NOTE = '复核结论不自动解除账号限制或恢复招募；实际变更须由有权限的管理员另行执行并留痕。'
REPORT_NOTE = '举报仅进入核实流程，不自动下架内容或限制账号；请在此记录查看处理反馈。'


def save(obj):
    obj.full_clean()
    obj.save()
    return obj


def require_login(actor):
    check(actor.is_authenticated and actor.is_active, 'login_required', '请先登录。', 403)


def lock_submitter(actor):
    require_login(actor)
    # 同一用户跨进程串行检查去重与配额，不能靠并发请求绕过。
    return get_user_model().objects.select_for_update().get(pk=actor.pk, is_active=True)


def check_limits(model, actor, now):
    rows = model.objects.filter(submitted_by=actor)
    day_limit, minute_limit = (10, 3) if model is Report else (5, 2)
    check(rows.filter(created_at__gte=now - timedelta(days=1)).count() < day_limit,
          'rate_limited', f'24 小时内最多提交 {day_limit} 条，请稍后再试。', 429)
    check(rows.filter(created_at__gte=now - timedelta(minutes=1)).count() < minute_limit,
          'rate_limited', '提交过于频繁，请一分钟后再试。', 429)


def text(value, label):
    check(isinstance(value, str) and 0 < len(value.strip()) <= 1000,
          'invalid_fields', f'{label}须为 1 至 1000 字符。', 400)
    return value.strip()


def report_target(kind, pk, actor):
    if kind == 'competition':
        public = Competition.objects.filter(publication_status='published').exclude(
            (Q(code__startswith='demo-r1-') | Q(code__startswith='demo-r2-')) & Q(title__startswith='【虚构样例】'))
        owned_ids = Team.objects.filter(Q(recruiter=actor) | Q(pk__in=Membership.objects.filter(user=actor).values('team_id')) |
            Q(pk__in=Application.objects.filter(applicant=actor).values('recruitment__team_id'))).values('competition_id')
        obj = Competition.objects.filter(Q(pk__in=public.values('pk')) | Q(pk__in=owned_ids)).get(pk=pk)
        return {'competition': obj}, obj.title[:240]
    check(kind == 'recruitment', 'invalid_fields', '只支持赛事或招募举报。', 400)
    from teams.views import public_cards
    owned = (Q(team__recruiter=actor) | Q(pk__in=Application.objects.filter(applicant=actor).values('recruitment_id')) |
        Q(team_id__in=Membership.objects.filter(user=actor, ended_at__isnull=True).values('team_id')))
    obj = Recruitment.objects.filter(Q(pk__in=public_cards().values('pk')) | owned).select_related('team__competition').get(pk=pk)
    return {'recruitment': obj}, f'{obj.team.competition.title} · {obj.code}'[:240]


def appeal_target(kind, pk, actor):
    if kind == 'restriction':
        obj = UserRestriction.objects.get(pk=pk, user=actor)
        return {'restriction': obj}, '账号新增发布和申请限制', obj.reason, obj.starts_at
    if kind == 'recruitment_action':
        obj = AdminAction.objects.select_related('recruitment__team__competition').get(
            pk=pk, action='withdraw', recruitment__team__recruiter=actor)
        return {'admin_action': obj}, f'招募下架 · {obj.recruitment.code}'[:240], obj.reason, obj.created_at
    check(kind == 'report', 'invalid_fields', '申诉对象类型无效。', 400)
    obj = Report.objects.exclude(status='pending').get(pk=pk, submitted_by=actor)
    return {'report': obj}, f'举报 #{obj.pk} 的处理结论', obj.feedback, obj.reviewed_at


@transaction.atomic
def submit_report(*, actor, data):
    actor = lock_submitter(actor)
    fields, title = report_target(data['target_type'], data['target_id'], actor)
    check(not Report.objects.filter(submitted_by=actor, status='pending', **fields).exists(),
          'duplicate_pending', '这个对象已有待处理举报，请在我的举报查看。')
    now = timezone.now()
    check_limits(Report, actor, now)
    check(data['reason'] in Report.Reason.values, 'invalid_fields', '问题类型无效。', 400)
    return save(Report(submitted_by=actor, target_title=title, description=text(data['description'], '说明'),
        reason=data['reason'], created_at=now, **fields))


@transaction.atomic
def submit_appeal(*, actor, data):
    actor = lock_submitter(actor)
    fields, title, _, _ = appeal_target(data['target_type'], data['target_id'], actor)
    check(not Appeal.objects.filter(submitted_by=actor, status='pending', **fields).exists(),
          'duplicate_pending', '这个对象已有待处理申诉，请等待另一位管理员复核。')
    now = timezone.now()
    check_limits(Appeal, actor, now)
    return save(Appeal(submitted_by=actor, target_title=title, description=text(data['description'], '申诉说明'), created_at=now, **fields))


@transaction.atomic
def review_record(model, pk, *, actor, outcome, feedback):
    require_login(actor)
    check(model in (Report, Appeal), 'invalid_fields', '处理类型无效。', 400)
    check(actor.is_staff and actor.has_perm(f'governance.change_{model._meta.model_name}'),
          'forbidden', '需要对应的举报或申诉处理权限。', 403)
    row = model.objects.select_for_update().get(pk=pk)
    check(row.status == 'pending', 'already_reviewed', '此记录已经处理，不能覆盖原结论。')
    check(actor.pk != row.submitted_by_id, 'review_conflict', '不能处理本人提交的记录。', 403)
    if model is Appeal:
        check(actor.pk != row.original_reviewer_id, 'review_conflict', '须由原处理人之外的管理员复核。', 403)
    check(outcome in model.Status.values and outcome != 'pending', 'invalid_fields', '处理结论无效。', 400)
    row.status, row.feedback = outcome, text(feedback, '处理反馈')
    row.reviewed_by, row.reviewed_at = actor, timezone.now()
    # 不调用下架/限制/恢复服务，避免把举报成立或申诉成立冒充实际处分变更。
    return save(row)


def target_choices(actor):
    require_login(actor)
    pending = Appeal.objects.filter(submitted_by=actor, status='pending')
    existing = {}
    for row in pending:
        kind, pk = ('restriction', row.restriction_id) if row.restriction_id else (
            ('recruitment_action', row.admin_action_id) if row.admin_action_id else ('report', row.report_id))
        existing[(kind, pk)] = row.pk
    candidates = []
    groups = [
        ('restriction', UserRestriction.objects.filter(user=actor)),
        ('recruitment_action', AdminAction.objects.filter(action='withdraw', recruitment__team__recruiter=actor).select_related('recruitment')),
        ('report', Report.objects.filter(submitted_by=actor).exclude(status='pending')),
    ]
    for kind, rows in groups:
        for row in rows:
            if kind == 'restriction':
                title, reason, occurred_at = '账号新增发布和申请限制', row.reason, row.starts_at
            elif kind == 'recruitment_action':
                title, reason, occurred_at = f'招募下架 · {row.recruitment.code}', row.reason, row.created_at
            else:
                title, reason, occurred_at = f'举报 #{row.pk} 的处理结论', row.feedback, row.reviewed_at
            pending_id = existing.get((kind, row.pk))
            candidates.append({'target_type': kind, 'target_id': row.pk, 'title': title, 'reason': reason,
                'occurred_at': occurred_at, 'can_appeal': not pending_id, 'pending_appeal_id': pending_id})
    return sorted(candidates, key=lambda item: (item['occurred_at'], item['target_id']), reverse=True)
