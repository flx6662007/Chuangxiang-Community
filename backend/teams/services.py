"""组队状态机。写入统一锁定、full_clean、事务消息；卡片读取不运行采集。"""
from contextlib import contextmanager
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.utils import timezone

from accounts.permissions import account_eligibility, school_email_verified
from competitions.models import Competition
from notifications.services import emit
from .errors import check
from .models import (
    Team, Recruitment, RecruitmentRevision, RecruitmentOption, RecruitmentBaselineMember,
    RecruitmentCurrentSkill, RecruitmentRequiredRole, RecruitmentRequiredSkill, RecruitmentCampus,
    Application, ApplicationRevision, ApplicationDesiredRole, ApplicationSkill,
    Membership, DepartureRequest, DissolutionRequest, DissolutionResponse,
)

LIVE = ['pending', 'contact_open']
SCALARS = ('existing_member_count', 'recruitment_quota', 'foundation_requirement',
           'weekly_effort', 'collaboration_goal', 'expected_duration', 'collaboration_mode')
MULTI = {'current_skills': RecruitmentCurrentSkill, 'required_roles': RecruitmentRequiredRole,
         'required_skills': RecruitmentRequiredSkill, 'campuses': RecruitmentCampus}


def save(obj):
    obj.full_clean()
    obj.save()
    return obj


@contextmanager
def lock_competition_graph(competition_id, extra_user_ids=()):
    """同届操作先稳定图，再按用户→赛事→队伍→卡片→申请→关系锁定。"""
    with transaction.atomic():
        if connection.vendor == 'postgresql':
            # 事务结束自动释放；稳定发现图，避免并发新队伍改变锁集合。
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [73491, competition_id])
        ids = set(extra_user_ids)
        ids.update(Team.objects.filter(competition_id=competition_id).values_list('recruiter_id', flat=True))
        ids.update(Application.objects.filter(recruitment__team__competition_id=competition_id).values_list('applicant_id', flat=True))
        ids.update(Membership.objects.filter(competition_id=competition_id).values_list('user_id', flat=True))
        list(get_user_model().objects.select_for_update().filter(pk__in=ids).order_by('pk'))
        competition = Competition.objects.select_for_update().get(pk=competition_id)
        list(Team.objects.select_for_update().filter(competition_id=competition_id).order_by('pk'))
        list(Recruitment.objects.select_for_update().filter(team__competition_id=competition_id).order_by('pk'))
        list(Application.objects.select_for_update().filter(recruitment__team__competition_id=competition_id).order_by('pk'))
        list(Membership.objects.select_for_update().filter(competition_id=competition_id).order_by('pk'))
        list(DepartureRequest.objects.select_for_update().filter(membership__competition_id=competition_id).order_by('pk'))
        list(DissolutionRequest.objects.select_for_update().filter(team__competition_id=competition_id).order_by('pk'))
        yield competition


def execute(competition_id, actor, action):
    """期限结算保留；非法动作回滚自己的修改，不撤销已经到期的结算。"""
    error = None
    result = None
    with lock_competition_graph(competition_id, [actor.pk] if actor else []):
        now = timezone.now()
        reconcile_competition(competition_id, now=now)
        try:
            with transaction.atomic():
                result = action(now)
        except Exception as exc:
            error = exc
    if error:
        raise error
    return result


def ensure_actor(actor, *, new=False):
    check(actor and actor.is_authenticated and actor.is_active, 'forbidden', '请使用有效账号登录。', 403)
    if new:
        eligibility = account_eligibility(actor)
        check(eligibility['eligible'], 'account_ineligible', '请先完成邮箱验证、联系资料和账号状态检查。', 403)


def ensure_member_eligible(user):
    # 24 小时发布限制只影响新建，不剥夺已有关系的处理权。
    check(user.is_active and school_email_verified(user) and user.has_contact_details,
          'account_ineligible', '入队双方须保持有效账号、已验证邮箱和联系资料。', 403)


def check_version(card, data, app=None):
    check(data.get('expected_version') == card.current_revision.version,
          'stale_version', '招募内容已更新，请刷新后操作。')
    if app:
        check(data.get('expected_application_version') == app.current_revision.version,
              'stale_version', '申请资料已更新，请刷新后操作。')


def ensure_open(card):
    check(card.is_open, 'card_unavailable', '当前招募已满员、暂停或结束，请刷新查看。')


def ensure_real_competition(competition):
    is_demo = competition.code.startswith(('demo-r1-', 'demo-r2-')) and competition.title.startswith('【虚构样例】')
    check(not is_demo, 'demo_unavailable', '该赛事为历史演示样例，不接受新的招募或申请。')


def recipients(app):
    return [app.applicant_id, app.recruitment.team.recruiter_id]


def clear_confirmations(app):
    for side in ('applicant', 'recruiter'):
        setattr(app, side + '_confirmed_at', None)
        setattr(app, side + '_confirmed_revision', None)


def finish_application(app, reason, now, actor=None):
    if app.status not in LIVE:
        return app
    app.status = reason if reason in ('withdrawn', 'rejected') else 'ended'
    app.end_reason = reason
    app.resolved_at = now
    clear_confirmations(app)
    save(app)
    kind = 'application_' + (reason if reason in ('withdrawn', 'rejected') else 'ended')
    emit(kind, target=app, recipients=recipients(app), actor=actor, payload={'reason': reason})
    return app


def close_card(card, reason, now, actor=None):
    if card.closed_at:
        return card
    card.closed_at, card.close_reason, card.closed_by = now, reason, actor
    save(card)
    app_reason = {'manual': 'card_closed'}.get(reason, reason)
    for app in Application.objects.filter(recruitment=card, status__in=LIVE):
        finish_application(app, app_reason, now, actor)
    emit('recruitment_closed', target=card, recipients=[card.team.recruiter_id], actor=actor,
         payload={'reason': reason})
    return card


def end_other_applications(user_id, competition_id, now, except_id=None):
    for app in Application.objects.filter(applicant_id=user_id, recruitment__team__competition_id=competition_id,
                                          status__in=LIVE).exclude(pk=except_id):
        finish_application(app, 'joined_other_team', now)


def end_member(member, reason, now):
    if member.ended_at:
        return
    member.ended_at, member.end_reason = now, reason
    save(member)
    for response in DissolutionResponse.objects.filter(membership=member, request__status='pending', excluded_at__isnull=True):
        response.excluded_at = now
        save(response)


def finish_departure(req, now, *, timeout=False):
    if timeout:
        req.status, req.resolved_at = 'timed_out', now
        save(req)
    end_member(req.membership, req.kind, now)
    emit('departure_completed', target=req, recipients=[req.initiator_id, req.responder_id],
         payload={'reason': req.status})


def finish_dissolution(req, now, reason):
    if req.status != 'pending':
        return
    req.status, req.completion_reason, req.resolved_at = 'completed', reason, now
    save(req)
    member_ids = list(req.team.active_members().values_list('user_id', flat=True))
    applicant_ids = list(Application.objects.filter(recruitment__team=req.team, status__in=LIVE).values_list('applicant_id', flat=True))
    for card in Recruitment.objects.filter(team=req.team, closed_at__isnull=True):
        close_card(card, 'team_dissolved', now)
    for app in Application.objects.filter(recruitment__team=req.team, status__in=LIVE):
        finish_application(app, 'team_dissolved', now)
    for departure in DepartureRequest.objects.filter(membership__team=req.team, status='pending'):
        departure.status, departure.resolved_at = 'team_dissolved', now
        save(departure)
        emit('departure_completed', target=departure, recipients=[departure.initiator_id, departure.responder_id],
             payload={'reason': 'team_dissolved'})
    for member in req.team.active_members():
        end_member(member, 'dissolution', now)
    team = req.team
    team.dissolved_at = now
    save(team)
    emit('dissolution_completed', target=req, recipients=member_ids + applicant_ids, payload={'reason': reason})


def maybe_finish_dissolution(req, now):
    if req.status != 'pending':
        return
    votes = DissolutionResponse.objects.filter(request=req, excluded_at__isnull=True)
    if votes.filter(response='reject').exists():
        req.status, req.resolved_at = 'rejected', now
        save(req)
        emit('dissolution_rejected', target=req, recipients=req.team.active_members().values_list('user_id', flat=True))
    elif not votes.exclude(response='agree').exists():
        finish_dissolution(req, now, 'all_agreed' if votes.exists() else 'no_other_members')
    elif now >= req.deadline_at:
        finish_dissolution(req, now, 'timeout')


def reconcile_competition(competition_id, now=None):
    """调用方必须已持有 lock_competition_graph；按同一个 now 结算全部联动。"""
    now = now or timezone.now()
    competition = Competition.objects.get(pk=competition_id)
    # 先依截止顺序结算；同刻整队解散优先，避免把已解散误记为个人退出。
    due = [(r.deadline_at, 0, r.pk, 'dissolution') for r in DissolutionRequest.objects.filter(
        team__competition_id=competition_id, status='pending', deadline_at__lte=now)]
    due += [(r.deadline_at, 1, r.pk, 'departure') for r in DepartureRequest.objects.filter(
        membership__competition_id=competition_id, status='pending', deadline_at__lte=now)]
    for _, _, pk, kind in sorted(due):
        if kind == 'dissolution':
            req = DissolutionRequest.objects.get(pk=pk)
            maybe_finish_dissolution(req, now)
        else:
            req = DepartureRequest.objects.select_related('membership').get(pk=pk)
            if req.status == 'pending':
                finish_departure(req, now, timeout=True)
    for req in DissolutionRequest.objects.filter(team__competition_id=competition_id, status='pending'):
        maybe_finish_dissolution(req, now)
    for card in Recruitment.objects.filter(team__competition_id=competition_id, publication_status='published', closed_at__isnull=True):
        reason = None
        if competition.publication_status != 'published':
            reason = 'competition_withdrawn'
        elif not competition.is_recruitment_open:
            reason = 'competition_stopped'
        elif card.expires_at and card.expires_at <= now:
            reason = 'expired'
        elif card.team.dissolved_at:
            reason = 'team_dissolved'
        if reason:
            close_card(card, reason, now)
        elif card.remaining_slots == 0:
            for app in Application.objects.filter(recruitment=card, status__in=LIVE):
                finish_application(app, 'full', now)
        elif not card.team.recruiter.is_active:
            close_card(card, 'manual', now)
    for app in Application.objects.filter(recruitment__team__competition_id=competition_id, status__in=LIVE):
        if not app.applicant.is_active:
            finish_application(app, 'account_disabled', now)
        elif app.recruitment.publication_status == 'withdrawn':
            finish_application(app, 'card_withdrawn', now)
        elif Membership.objects.filter(user_id=app.applicant_id, competition_id=competition_id, ended_at__isnull=True).exists():
            finish_application(app, 'joined_other_team', now)


def assign_options(revision, data, mappings):
    for field, model in mappings.items():
        codes = data.get(field, [])
        options = list(RecruitmentOption.objects.select_for_update().filter(code__in=codes).order_by('pk'))
        check(len(options) == len(set(codes)), 'invalid_fields', '所选词条不存在。', 400)
        for option in options:
            save(model(revision=revision, option=option))


def card_data(revision):
    result = {key: getattr(revision, key) for key in SCALARS}
    result.update({key: sorted(getattr(revision, key).values_list('code', flat=True)) for key in MULTI})
    return result


def build_card_revision(card, actor, data, now):
    rev = save(RecruitmentRevision(recruitment=card, version=card.current_revision.version + 1 if card.current_revision_id else 1,
                                  edited_by=actor, created_at=now, **{key: data[key] for key in SCALARS}))
    assign_options(rev, data, MULTI)
    for member in card.team.active_members().exclude(application__recruitment_id=card.pk):
        save(RecruitmentBaselineMember(revision=rev, membership=member))
    rev.validate_ready()
    return rev


def preview_recruitment(*, actor, data):
    # 复用完整发布校验并回滚保存点，不产生预览草稿、关系或系统通知。
    with transaction.atomic():
        card = publish_recruitment(actor=actor, data=data)
        result = {'expires_at': card.expires_at, 'server_time': card.published_at, 'duration_days': card.duration_days}
        transaction.set_rollback(True)
    return result


def publish_recruitment(*, actor, data):
    def action(now):
        ensure_actor(actor, new=True)
        competition = Competition.objects.get(pk=data['competition_id'])
        ensure_real_competition(competition)
        check(competition.is_recruitment_open, 'card_unavailable', '该赛事当前不允许招募。')
        if data.get('team_id'):
            team = Team.objects.get(pk=data['team_id'])
            check(team.recruiter_id == actor.pk, 'forbidden', '只能为自己发起的队伍发布。', 403)
            check(team.competition_id == competition.pk and not team.dissolved_at, 'invalid_fields', '队伍赛事不符或已经解散。', 400)
            check(not team.is_dissolution_pending, 'team_paused', '解散等待中暂停招募。')
        else:
            check(not Membership.objects.filter(user=actor, competition=competition, ended_at__isnull=True).exists(),
                  'already_member', '同届已有正式队伍，不能再创建队伍。')
            team = save(Team(competition=competition, recruiter=actor, created_at=now))
            save(Membership(team=team, competition=competition, user=actor, join_source='recruiter', joined_at=now))
            end_other_applications(actor.pk, competition.pk, now)
        check(not Recruitment.objects.filter(team=team, publication_status='published', closed_at__isnull=True).exists(),
              'active_card_exists', '同队只能保留一张有效招募卡，满员卡须先关闭。')
        card = save(Recruitment(team=team, duration_days=data['duration_days'], created_at=now))
        rev = build_card_revision(card, actor, data, now)
        card.current_revision, card.published_at, card.last_edited_at = rev, now, now
        card.expires_at = min(now + timedelta(days=card.duration_days), competition.recruitment_deadline) if competition.recruitment_deadline else now + timedelta(days=card.duration_days)
        card.publication_status = 'published'
        return save(card)
    return execute(data['competition_id'], actor, action)


def edit_recruitment(card_id, *, actor, data):
    competition_id = Recruitment.objects.values_list('team__competition_id', flat=True).get(pk=card_id)
    def action(now):
        card = Recruitment.objects.get(pk=card_id)
        ensure_actor(actor)
        check(card.team.recruiter_id == actor.pk, 'forbidden', '只有招募者可编辑。', 403)
        check_version(card, data)
        check(not card.closed_at and card.publication_status == 'published' and card.expires_at > now,
              'card_unavailable', '已结束卡片不能编辑或续期。')
        check(not card.team.is_dissolution_pending, 'team_paused', '解散等待中暂停编辑。')
        old = card_data(card.current_revision)
        # 旧轮成员离开已自动减少展示基数；编辑其他内容不能默默把人数补回。
        old['existing_member_count'] = card.current_existing_member_count
        updated = {**old, **{k: sorted(v) if k in MULTI else v for k, v in data.items() if k in old}}
        changed = [key for key in old if old[key] != updated[key]]
        if not changed:
            return card
        old_version = card.current_revision.version
        card.current_revision = build_card_revision(card, actor, updated, now)
        card.last_edited_at = now
        save(card)
        viewers = list(card.team.active_members().values_list('user_id', flat=True))
        for app in Application.objects.filter(recruitment=card, status__in=LIVE):
            viewers.append(app.applicant_id)
            clear_confirmations(app)
            save(app)
        emit('recruitment_edited', target=card, recipients=viewers, actor=actor,
             payload={'from_version': old_version, 'to_version': card.current_revision.version, 'changed_fields': changed})
        if card.remaining_slots == 0:
            for app in Application.objects.filter(recruitment=card, status__in=LIVE):
                finish_application(app, 'full', now)
        return card
    return execute(competition_id, actor, action)


def close_recruitment(card_id, *, actor, data):
    competition_id = Recruitment.objects.values_list('team__competition_id', flat=True).get(pk=card_id)
    def action(now):
        card = Recruitment.objects.get(pk=card_id)
        check(actor.pk == card.team.recruiter_id, 'forbidden', '只有招募者可关闭。', 403)
        check_version(card, data)
        return close_card(card, 'manual', now, actor) if not card.closed_at else card
    return execute(competition_id, actor, action)


def withdraw_recruitment(card_id, *, actor, reason):
    check(actor.is_active and actor.is_staff and actor.has_perm('teams.change_recruitment'),
          'forbidden', '需要招募管理权限。', 403)
    check(isinstance(reason, str) and 0 < len(reason.strip()) <= 500, 'invalid_fields', '填写 1 至 500 字的核实下架理由。', 400)
    competition_id = Recruitment.objects.values_list('team__competition_id', flat=True).get(pk=card_id)
    def action(now):
        from governance.models import AdminAction
        card = Recruitment.objects.get(pk=card_id)
        if card.publication_status == 'withdrawn':
            return card
        check(card.publication_status == 'published', 'invalid_state', '只能下架已发布招募。')
        card.publication_status, card.withdrawn_at, card.withdrawal_reason = 'withdrawn', now, reason.strip()
        save(card)
        for app in Application.objects.filter(recruitment=card, status__in=LIVE):
            finish_application(app, 'card_withdrawn', now, actor)
        save(AdminAction(action='withdraw', recruitment=card, actor=actor, reason=reason.strip(),
                         changes={'before_status': 'published', 'after_status': 'withdrawn'}))
        return card
    return execute(competition_id, actor, action)


def build_application_revision(app, actor, data, now):
    revision = save(ApplicationRevision(application=app,
        version=app.current_revision.version + 1 if app.current_revision_id else 1,
        recruitment_revision=app.recruitment.current_revision, weekly_effort=data['weekly_effort'],
        accepted_at=now, created_by=actor))
    assign_options(revision, data, {'desired_roles': ApplicationDesiredRole, 'skills': ApplicationSkill})
    app.current_revision = revision
    clear_confirmations(app)
    return save(app)


def submit_application(card_id, *, actor, data):
    competition_id = Recruitment.objects.values_list('team__competition_id', flat=True).get(pk=card_id)
    def action(now):
        card = Recruitment.objects.get(pk=card_id)
        ensure_actor(actor, new=True)
        ensure_real_competition(card.team.competition)
        check_version(card, data)
        ensure_open(card)
        check(actor.pk != card.team.recruiter_id, 'forbidden', '不能申请自己的招募。', 403)
        check(not Membership.objects.filter(user=actor, competition_id=competition_id, ended_at__isnull=True).exists(),
              'already_member', '本届已有正式队伍。')
        check(not Application.objects.filter(recruitment=card, applicant=actor).exists(),
              'already_applied', '同一卡片只能申请一次，结束后可选择新的招募卡。')
        app = save(Application(recruitment=card, applicant=actor, submitted_at=now))
        build_application_revision(app, actor, data, now)
        emit('application_submitted', target=app, recipients=[card.team.recruiter_id], actor=actor)
        return app
    return execute(competition_id, actor, action)


def application_action(app_id, *, actor, action, data):
    competition_id = Application.objects.values_list('recruitment__team__competition_id', flat=True).get(pk=app_id)
    def perform(now):
        app = Application.objects.get(pk=app_id)
        card = app.recruitment
        ensure_actor(actor)
        party = 'applicant' if actor.pk == app.applicant_id else 'recruiter' if actor.pk == card.team.recruiter_id else None
        check(party is not None, 'forbidden', '只有申请双方可操作。', 403)
        check_version(card, data, app)
        required_party = {'accept': 'recruiter', 'reject': 'recruiter', 'withdraw': 'applicant',
                          'end': 'recruiter', 'continue': 'applicant'}.get(action)
        check(not required_party or required_party == party, 'forbidden', '当前身份不能执行此操作。', 403)
        # 已完成重试仅返回现状，不新增关系或重复事件。
        if action == 'confirm' and app.status == 'joined':
            return app
        if action == 'accept' and app.status == 'contact_open':
            return app
        if (action, app.status) in [('withdraw', 'withdrawn'), ('reject', 'rejected')]:
            return app
        if action == 'end' and app.end_reason == 'recruiter_terminated':
            return app
        check(app.status in LIVE, 'application_resolved', '申请已经结束，不能重开。')
        if action in ('withdraw', 'reject', 'end'):
            if action == 'reject':
                check(app.status == 'pending', 'invalid_state', '已接受的申请请使用结束申请。')
            if action == 'end':
                check(app.status == 'contact_open', 'invalid_state', '尚未接受的申请请使用拒绝。')
            return finish_application(app, {'withdraw': 'withdrawn', 'reject': 'rejected', 'end': 'recruiter_terminated'}[action], now, actor)
        if action == 'revoke-confirmation':
            if getattr(app, party + '_confirmed_at'):
                setattr(app, party + '_confirmed_at', None)
                setattr(app, party + '_confirmed_revision', None)
                save(app)
                emit('confirmation_revoked', target=app, recipients=recipients(app), actor=actor, payload={'party': party, 'revision': app.current_revision.version})
            return app
        ensure_open(card)
        if action == 'continue':
            check(app.current_revision.recruitment_revision_id != card.current_revision_id,
                  'invalid_state', '尚无新的招募版本需要接受。')
            old_version = app.current_revision.version
            build_application_revision(app, actor, data, now)
            emit('application_continued', target=app, recipients=[card.team.recruiter_id], actor=actor,
                 payload={'from_version': old_version, 'to_version': app.current_revision.version})
            return app
        check(not app.is_paused, 'application_paused', '请申请人先接受最新条件，或等待解散请求结束。')
        if action == 'accept':
            app.status, app.contact_opened_at = 'contact_open', now
            save(app)
            emit('contact_opened', target=app, recipients=recipients(app), actor=actor)
            return app
        check(action == 'confirm' and app.status == 'contact_open', 'invalid_state', '须先接受联系，再分别确认入队。')
        ensure_member_eligible(app.applicant)
        ensure_member_eligible(card.team.recruiter)
        check(not Membership.objects.filter(user=app.applicant, competition_id=competition_id, ended_at__isnull=True).exists(),
              'already_member', '申请人本届已有正式队伍。')
        if getattr(app, party + '_confirmed_at'):
            return app
        setattr(app, party + '_confirmed_at', now)
        setattr(app, party + '_confirmed_revision', app.current_revision)
        if app.applicant_confirmed_at and app.recruiter_confirmed_at:
            save(Membership(team=card.team, competition_id=competition_id, user=app.applicant,
                            application=app, join_source='application', joined_at=now))
            app.status, app.end_reason, app.resolved_at = 'joined', 'joined', now
            save(app)
            emit('member_joined', target=app, recipients=recipients(app), actor=actor)
            end_other_applications(app.applicant_id, competition_id, now, app.pk)
            if card.remaining_slots == 0:
                for other in Application.objects.filter(recruitment=card, status__in=LIVE):
                    finish_application(other, 'full', now)
        else:
            save(app)
            emit('application_confirmed', target=app, recipients=recipients(app), actor=actor,
                 payload={'party': party, 'revision': app.current_revision.version})
        return app
    return execute(competition_id, actor, perform)


def request_departure(member_id, *, actor, kind):
    competition_id = Membership.objects.values_list('competition_id', flat=True).get(pk=member_id)
    def action(now):
        member = Membership.objects.get(pk=member_id)
        ensure_actor(actor)
        check(not member.ended_at and not member.team.dissolved_at, 'membership_ended', '成员关系已结束。')
        initiator = member.user_id if kind == 'exit' else member.team.recruiter_id
        responder = member.team.recruiter_id if kind == 'exit' else member.user_id
        check(actor.pk == initiator and member.user_id != member.team.recruiter_id,
              'forbidden', '只有对应成员或招募者可发起，招募者本人请使用解散。', 403)
        old = DepartureRequest.objects.filter(membership=member, status='pending').first()
        if old:
            check(old.initiator_id == actor.pk and old.kind == kind, 'request_pending', '已有另一方发起的待处理请求。')
            return old
        req = save(DepartureRequest(membership=member, kind=kind, initiator_id=initiator,
                  responder_id=responder, created_at=now, deadline_at=now + timedelta(hours=24)))
        emit('departure_requested', target=req, recipients=[initiator, responder], actor=actor)
        return req
    return execute(competition_id, actor, action)


def departure_action(request_id, *, actor, action, response=None):
    competition_id = DepartureRequest.objects.values_list('membership__competition_id', flat=True).get(pk=request_id)
    def perform(now):
        req = DepartureRequest.objects.get(pk=request_id)
        check(actor.pk == (req.initiator_id if action == 'withdraw' else req.responder_id),
              'forbidden', '无权处理该请求。', 403)
        if req.status != 'pending':
            return req
        if action == 'withdraw':
            req.status, req.resolved_at = 'withdrawn', now
            save(req)
            emit('departure_withdrawn', target=req, recipients=[req.initiator_id, req.responder_id], actor=actor)
        else:
            req.response, req.responded_at, req.resolved_at = response, now, now
            req.status = 'approved' if response == 'agree' else 'rejected'
            save(req)
            emit('departure_responded', target=req, recipients=[req.initiator_id, req.responder_id], actor=actor)
            if response == 'agree':
                finish_departure(req, now)
                for dissolution in DissolutionRequest.objects.filter(team=req.membership.team, status='pending'):
                    maybe_finish_dissolution(dissolution, now)
        return req
    return execute(competition_id, actor, perform)


def request_dissolution(team_id, *, actor):
    competition_id = Team.objects.values_list('competition_id', flat=True).get(pk=team_id)
    def action(now):
        team = Team.objects.get(pk=team_id)
        check(actor.pk == team.recruiter_id, 'forbidden', '只有招募者可发起解散。', 403)
        check(not team.dissolved_at, 'team_dissolved', '队伍已解散。')
        old = DissolutionRequest.objects.filter(team=team, status='pending').first()
        if old:
            return old
        req = save(DissolutionRequest(team=team, initiator=actor, created_at=now, deadline_at=now + timedelta(hours=24)))
        for member in team.active_members().exclude(user=actor):
            save(DissolutionResponse(request=req, membership=member))
        emit('dissolution_requested', target=req, recipients=team.active_members().values_list('user_id', flat=True), actor=actor)
        maybe_finish_dissolution(req, now)
        return req
    return execute(competition_id, actor, action)


def dissolution_action(request_id, *, actor, action, response=None):
    competition_id = DissolutionRequest.objects.values_list('team__competition_id', flat=True).get(pk=request_id)
    def perform(now):
        req = DissolutionRequest.objects.get(pk=request_id)
        if action == 'withdraw':
            check(req.initiator_id == actor.pk, 'forbidden', '只有发起人可撤回。', 403)
            if req.status != 'pending':
                return req
            req.status, req.resolved_at = 'withdrawn', now
            save(req)
            emit('dissolution_withdrawn', target=req, recipients=req.team.active_members().values_list('user_id', flat=True), actor=actor)
        else:
            vote = DissolutionResponse.objects.filter(request=req, membership__user=actor).first()
            check(vote is not None, 'forbidden', '你不在本次解散回应名单中。', 403)
            if req.status != 'pending':
                return req
            check(vote.excluded_at is None, 'membership_ended', '已离队成员无需回应。')
            if vote.response:
                check(vote.response == response, 'request_resolved', '本次已回应，不能改答。')
                return req
            vote.response, vote.responded_at = response, now
            save(vote)
            emit('dissolution_responded', target=req, recipients=[req.initiator_id], actor=actor)
            maybe_finish_dissolution(req, now)
        return req
    return execute(competition_id, actor, perform)
