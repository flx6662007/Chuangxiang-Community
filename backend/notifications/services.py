"""仅系统业务通知，与调用方业务事务一并保存，不发送外部消息。"""
from .models import BusinessEvent, Notification


def emit(kind, *, target, recipients, actor=None, payload=None):
    field = {'Recruitment': 'recruitment', 'Application': 'application',
             'DepartureRequest': 'departure_request', 'DissolutionRequest': 'dissolution_request'}[type(target).__name__]
    event = BusinessEvent(kind=kind, actor=actor, payload=payload or {}, **{field: target})
    event.full_clean()
    event.save()
    titles = {
        'recruitment_edited': '招募条件已更新，请查看最新内容',
        'recruitment_closed': '招募已结束', 'application_submitted': '收到新的入队申请',
        'contact_opened': '已开放联系方式，沟通后双方确认入队',
        'application_confirmed': '对方已确认入队', 'confirmation_revoked': '对方已撤销本次确认',
        'application_continued': '申请人已接受最新招募条件', 'application_withdrawn': '申请已撤回',
        'application_rejected': '申请未被接受', 'application_ended': '申请已结束',
        'member_joined': '双方确认完成，已正式入队', 'departure_requested': '收到退出或移除请求',
        'departure_responded': '退出或移除请求已有回应', 'departure_withdrawn': '退出或移除请求已撤回',
        'departure_completed': '成员关系已结束', 'dissolution_requested': '收到整队解散请求',
        'dissolution_responded': '解散请求已有回应', 'dissolution_withdrawn': '解散请求已撤回',
        'dissolution_rejected': '解散请求被拒绝，成员关系保留', 'dissolution_completed': '队伍已解散',
    }
    body = '请在我的组队查看当前状态；站内确认不代替赛事官方报名。'
    if kind in ('application_confirmed', 'confirmation_revoked'):
        party = {'applicant': '申请人', 'recruiter': '招募者'}[payload['party']]
        titles[kind] = party + ('已确认入队' if kind == 'application_confirmed' else '已撤销本次确认')
    if kind == 'recruitment_edited':
        labels = {'existing_member_count': '已有成员数', 'recruitment_quota': '招募名额',
            'current_skills': '现有能力', 'required_roles': '招募角色', 'required_skills': '所需技能',
            'foundation_requirement': '基础要求', 'weekly_effort': '每周投入', 'collaboration_goal': '合作目标',
            'expected_duration': '合作时长', 'collaboration_mode': '协作方式', 'campuses': '校区'}
        body = '变更字段：' + '、'.join(labels[key] for key in payload['changed_fields']) + '。未入队申请须主动继续，阅读消息不代表接受。'
    for user_id in sorted(set(recipients)):
        note = Notification(event=event, recipient_id=user_id, title=titles[kind], body=body)
        note.full_clean()
        note.save()
    return event
