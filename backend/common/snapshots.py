"""只保存可解释、限长的 JSON；不接收任意请求对象。"""
import json

from django.core.exceptions import ValidationError


def json_object(value, allowed, required=(), max_chars=30000):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValidationError('JSON 字段必须为符合约定键集的对象。')
    if len(json.dumps(value, ensure_ascii=False)) > max_chars:
        raise ValidationError('JSON 内容超出约定长度。')


PUBLIC_SNAPSHOT_KEYS = {
    'code','title','description','summary','recruiting_entity','official_url','official_source_name',
    'supervisor','research_group','institution','category','work_content','eligibility','requirements',
    'vacancies_text','vacancies_min','vacancies_max','weekly_hours_text','weekly_hours_min','weekly_hours_max',
    'duration_text','starts_on','ends_on','collaboration_mode','location_text','application_instructions',
    'application_url','application_email','deadline_mode','deadline_on','deadline_at','deadline_timezone',
    'deadline_notes','closed_at','closure_note','provider','access_url','source_note','availability',
    'content_version','tags','directions','competitions','research_opportunities','sources',
}


def content_snapshot(value):
    json_object(value, PUBLIC_SNAPSHOT_KEYS, required=('title', 'content_version'), max_chars=100000)
    if not isinstance(value['title'], str) or type(value['content_version']) is not int or value['content_version'] < 1:
        raise ValidationError('快照标题/版本类型错误。')
