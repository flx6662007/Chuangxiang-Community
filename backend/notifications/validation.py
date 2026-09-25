from common.models import require
from common.snapshots import json_object


EDITABLE_CARD_FIELDS = {'existing_member_count','recruitment_quota','current_skills','required_roles','required_skills','foundation_requirement','weekly_effort','collaboration_goal','expected_duration','collaboration_mode','campuses'}


def validate_model(obj):
    if type(obj).__name__ != 'BusinessEvent':
        return
    if obj.kind.startswith('recruitment_'):
        target='recruitment'
    elif obj.kind.startswith('departure_'):
        target='departure_request'
    elif obj.kind.startswith('dissolution_'):
        target='dissolution_request'
    elif obj.kind == 'admin_action':
        target='admin_action'
    else:
        target='application'
    require(getattr(obj,target+'_id') is not None, '事件与目标类型不匹配。')
    allowed = {'from_version','to_version','changed_fields'} if obj.kind == 'recruitment_edited' else {'reason','party','revision','from_version','to_version'}
    required = allowed if obj.kind == 'recruitment_edited' else ()
    json_object(obj.payload, allowed, required)
    for key in ['from_version','to_version','revision']:
        if key in obj.payload:
            require(type(obj.payload[key]) is int and obj.payload[key] >= 1, '事件版本号必须为正整数。')
    if 'party' in obj.payload:
        require(obj.payload['party'] in ['applicant','recruiter'], '确认方无效。')
    if obj.kind == 'recruitment_edited':
        fields=obj.payload['changed_fields']
        require(isinstance(fields,list) and fields and all(isinstance(x,str) and x in EDITABLE_CARD_FIELDS for x in fields), '变更字段必须为允许的卡片字段列表。')
        require(obj.payload['to_version'] == obj.payload['from_version']+1, '卡片变更版本须连续。')
    if 'reason' in obj.payload:
        require(isinstance(obj.payload['reason'],str) and len(obj.payload['reason']) <= 80, '原因仅保存有限长度的系统原因码。')
