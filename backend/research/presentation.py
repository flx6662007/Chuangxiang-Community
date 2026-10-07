"""Explicit public card schema; audit prose is never used as a display fallback."""
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date

PROFILE_TEXT = ('direction', 'location', 'achievements')
RECRUITMENT_FIELDS = ('roles', 'eligibility', 'work', 'commitment', 'scope', 'cohort', 'deadline', 'status')
LINK_FIELDS = ('summary', *PROFILE_TEXT, *RECRUITMENT_FIELDS, 'recruitment')


def validate_card_details(value):
    if not isinstance(value, dict) or set(value) - {*PROFILE_TEXT, 'recruitment', 'hasRecruitmentSource', 'fieldLinks'}:
        raise ValidationError('科研展示字段结构无效。')
    recruitment = value.get('recruitment', {})
    if not isinstance(recruitment, dict) or set(recruitment) - set(RECRUITMENT_FIELDS):
        raise ValidationError('招募展示字段结构无效。')
    strings = [value[k] for k in PROFILE_TEXT if k in value] + list(recruitment.values())
    if any(not isinstance(s, str) or len(s) > 5000 for s in strings):
        raise ValidationError('展示字段必须为不超过 5000 字的文本。')
    if 'hasRecruitmentSource' in value and type(value['hasRecruitmentSource']) is not bool:
        raise ValidationError('招募来源标记必须为布尔值。')
    from information_library.selectors import safe_source_url
    field_links = value.get('fieldLinks', {})
    if not isinstance(field_links, dict) or set(field_links) - set(LINK_FIELDS):
        raise ValidationError('字段来源映射无效。')
    for links in field_links.values():
        if not isinstance(links, list) or len(links) > 3:
            raise ValidationError('每个字段最多关联三条来源。')
        seen = set()
        for link in links:
            if (not isinstance(link, dict) or set(link) != {'label', 'url'}
                    or not isinstance(link['label'], str) or not 1 <= len(link['label'].strip()) <= 40
                    or not safe_source_url(link['url']) or link['url'] in seen):
                raise ValidationError('字段来源须包含简短标题和不重复的公开链接。')
            seen.add(link['url'])


def public_card_details(value):
    from information_library.selectors import public_text
    validate_card_details(value)
    return {**{k: public_text(value.get(k, '')) for k in PROFILE_TEXT},
            'recruitment': {k: public_text(v) for k, v in value.get('recruitment', {}).items() if v},
            'fieldLinks': {k: [{'label': public_text(link['label']), 'url': link['url']} for link in links]
                           for k, links in value.get('fieldLinks', {}).items()},
            'hasRecruitmentSource': value.get('hasRecruitmentSource', False)}


def has_recruitment_opportunity(card):
    details = card.get('details', {})
    recruitment = details.get('recruitment', {})
    if not details.get('hasRecruitmentSource') or recruitment.get('status') in {'历史批次', '已结束'}:
        return False
    try:
        deadline = date.fromisoformat(recruitment.get('deadline', '')[:10])
    except ValueError:
        return True
    return deadline >= timezone.localdate()
