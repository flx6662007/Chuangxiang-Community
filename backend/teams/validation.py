"""关系校验；并发人数、角色权限与状态联动仍须锁内事务服务。"""
from django.core.exceptions import ValidationError
from django.utils import timezone

from common.models import require


def validate_model(obj):
    name = type(obj).__name__
    old = None if obj._state.adding else type(obj).objects.filter(pk=obj.pk).first()
    if name == 'Recruitment':
        if obj.current_revision_id:
            require(obj.current_revision.recruitment_id == obj.pk, '当前版本必须属于本卡。')
        if old and old.published_at:
            require(obj.duration_days == old.duration_days and obj.expires_at == old.expires_at, '编辑不改变有效期。')
        if old and old.closed_at:
            require(obj.closed_at == old.closed_at and obj.close_reason == old.close_reason, '已关闭卡片不能重开。')
        if obj.publication_status == 'published' and obj.current_revision_id and (
                not old or old.current_revision_id != obj.current_revision_id or old.publication_status != 'published'):
            obj.current_revision.validate_ready()
    elif name == 'RecruitmentRevision':
        require(obj.edited_by_id == obj.recruitment.team.recruiter_id, '招募版本编辑人须为招募者。')
        current = obj.recruitment.current_revision
        if obj._state.adding:
            require(not current or obj.version == current.version + 1, '新卡片版本必须连续递增。')
            if not current:
                require(obj.version == 1, '初始版本为 1。')
        if obj._state.adding:
            validate_capacity(obj)
    elif name == 'RecruitmentBaselineMember':
        card, member = obj.revision.recruitment, obj.membership
        require(member.team_id == card.team_id, '基数成员必须来自本队。')
        require(not member.application_id or member.application.recruitment_id != card.pk, '本卡应募成员不能重复计入基数。')
        if obj._state.adding:
            require(member.ended_at is None, '不能把已退出成员新增到基数。')
            require(not card.current_revision_id or card.current_revision.version < obj.revision.version, '已生效基数快照不能追加。')
    elif name == 'Application':
        require(obj.applicant_id != obj.recruitment.team.recruiter_id, '招募者不能申请自己的卡片。')
        if obj.current_revision_id:
            require(obj.current_revision.application_id == obj.pk, '当前资料必须属于本申请。')
        for side in ['applicant', 'recruiter']:
            revision = getattr(obj, side + '_confirmed_revision')
            if revision:
                require(revision.application_id == obj.pk and revision.pk == obj.current_revision_id, '正式确认必须针对本申请当前资料版本。')
        if old and old.status in ['joined', 'withdrawn', 'rejected', 'ended']:
            require(all(getattr(obj,f.attname) == getattr(old,f.attname) for f in obj._meta.fields), '终结申请不能重开或改写。')
        if old and old.contact_opened_at:
            require(obj.contact_opened_at == old.contact_opened_at, '首次开放联系方式时间不重置。')
    elif name == 'ApplicationRevision':
        require(obj.created_by_id == obj.application.applicant_id, '申请资料只能属于申请人。')
        require(obj.recruitment_revision.recruitment_id == obj.application.recruitment_id, '不能接受别的卡片版本。')
        if obj._state.adding:
            current = obj.application.current_revision
            require(obj.version == (current.version + 1 if current else 1), '资料版本须连续递增。')
            require(obj.recruitment_revision_id == obj.application.recruitment.current_revision_id, '只能接受当前卡片版本。')
            require(not current or current.recruitment_revision_id != obj.recruitment_revision_id, '只有条件更新后继续申请才能建立新资料版本。')
            require(obj.application.status in ['pending', 'contact_open'], '已结束申请不能新增资料。')
    elif name == 'Membership':
        require(obj.competition_id == obj.team.competition_id, '成员赛事必须与队伍一致。')
        if obj.join_source == 'recruiter':
            require(obj.user_id == obj.team.recruiter_id, '招募者成员必须对应队伍招募者。')
        elif obj.application_id:
            app = obj.application
            require(app.applicant_id == obj.user_id and app.recruitment.team_id == obj.team_id, '成员与申请人、队伍不匹配。')
    elif name == 'DepartureRequest':
        member = obj.membership
        recruiter = member.team.recruiter_id
        require(member.user_id != recruiter, '招募者使用解散流程离队。')
        expected = (member.user_id, recruiter) if obj.kind == 'exit' else (recruiter, member.user_id)
        require((obj.initiator_id, obj.responder_id) == expected, '发起/回应双方与请求类型不匹配。')
        if obj._state.adding:
            require(member.ended_at is None, '成员已离队。')
        if obj.responded_at:
            require(obj.created_at <= obj.responded_at < obj.deadline_at, '实际回应须发生在截止前。')
        if obj.status == 'timed_out' and obj.resolved_at:
            require(obj.resolved_at >= obj.deadline_at, '未到期限不能按超时完成。')
        if obj.status == 'withdrawn' and obj.resolved_at:
            require(obj.resolved_at < obj.deadline_at, '截止后不能撤回。')
        freeze_request(old, obj)
    elif name == 'DissolutionRequest':
        require(obj.initiator_id == obj.team.recruiter_id, '只有招募者可发起解散。')
        if obj._state.adding:
            require(obj.team.dissolved_at is None, '队伍已解散。')
        if obj.completion_reason == 'timeout' and obj.resolved_at:
            require(obj.resolved_at >= obj.deadline_at, '未到期限不能超时解散。')
        if obj.status == 'withdrawn' and obj.resolved_at:
            require(obj.resolved_at < obj.deadline_at, '截止后不能撤回。')
        freeze_request(old, obj)
    elif name == 'DissolutionResponse':
        require(obj.membership.team_id == obj.request.team_id, '回应成员不属于该队伍。')
        require(obj.membership.user_id != obj.request.team.recruiter_id, '招募者不重复投票。')
        if obj.responded_at:
            require(obj.request.created_at <= obj.responded_at < obj.request.deadline_at, '回应须发生在截止前。')
        if old and old.response:
            require(obj.response == old.response and obj.responded_at == old.responded_at, '已作回应不能改答。')
        if (not old or not old.response) and obj.response:
            require(obj.request.status == 'pending' and obj.excluded_at is None, '请求已结束或成员已退出。')
        if obj.excluded_at:
            require(obj.membership.ended_at is not None, '只有已离队成员可排除。')


def freeze_request(old, obj):
    if old:
        fields = ['created_at', 'deadline_at', 'initiator_id']
        fields += ['membership_id', 'responder_id', 'kind'] if hasattr(obj,'membership_id') else ['team_id']
        require(all(getattr(old,f) == getattr(obj,f) for f in fields), '不能更换请求双方、重设截止或所属关系。')
        if old.status != 'pending':
            require(all(getattr(old,f.attname) == getattr(obj,f.attname) for f in obj._meta.fields), '已结束请求不能重开。')


def validate_capacity(obj):
    known = obj.recruitment.team.active_members().exclude(application__recruitment_id=obj.recruitment_id).count()
    require(obj.existing_member_count >= known, '已有人数不能少于平台已知基数成员。')
    require(obj.recruitment_quota >= obj.recruitment.joined_member_count, '招募名额不能少于本卡当前成功应募人数。')
    if obj.version == 1:
        require(obj.recruitment_quota >= 1, '首次发布至少招募 1 人。')
    maximum = obj.recruitment.team.competition.team_size_max
    require(maximum is None or obj.existing_member_count + obj.recruitment_quota <= maximum,
            '声明人数加计划招募人数超过赛事人数上限。')
