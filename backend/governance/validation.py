from common.models import require
from common.snapshots import json_object


def validate_model(obj):
    if type(obj).__name__ != 'AdminAction':
        return
    json_object(obj.changes, {'before_status','after_status','fields','before_version','after_version'})
    if obj.restriction_id:
        require(obj.target_user_id == obj.restriction.user_id, '限制记录与被处理用户不一致。')
    if obj.action in ['restrict','revoke_restriction','disable_account','enable_account']:
        require(obj.target_user_id is not None, '账号动作必须指向用户。')
    if obj.action in ['restrict','revoke_restriction']:
        require(obj.restriction_id is not None, '限制动作须关联限制记录。')
    if obj.reverses_id:
        original = obj.reverses
        expected = {'restore':'withdraw','revoke_restriction':'restrict','enable_account':'disable_account'}
        require(expected.get(obj.action) == original.action, '撤销动作不匹配。')
        require(all(getattr(obj,f+'_id') == getattr(original,f+'_id') for f in ['target_user','competition','research','resource','newsletter','recruitment','restriction']), '撤销须对应同一对象。')
