"""Public research facts shared by retrieval, citations and recommendation cards.

Only curated field text is evidence. A linked page is not an imported full text.
"""
import hashlib
import json
from urllib.parse import urldefrag

from .presentation import public_card_details, has_recruitment_opportunity

LABELS = {
    'summary': '研究内容', 'direction': '研究方向', 'location': '研究地点',
    'achievements': '研究成果', 'roles': '招募对象', 'eligibility': '申请条件',
    'work': '参与工作', 'commitment': '时间投入', 'scope': '申请范围',
    'cohort': '招募批次', 'deadline': '申请截止', 'status': '招募状态',
    'recruitment': '招募入口',
}
RECRUITMENT_KEYS = ('roles', 'eligibility', 'work', 'commitment', 'scope', 'cohort', 'deadline', 'status')


def source_key(url):
    return urldefrag(url)[0].rstrip('/')


def research_facts(*, summary, institution, details, primary_url, verified_at,
                   published_on=None, sources=(), legacy=None, closed=False):
    from information_library.selectors import public_text, safe_source_url
    profile = public_card_details(details)
    # Source dates belong to each actual page, never to the record's import date.
    verified = {source_key(primary_url): {'verified_at': verified_at, 'published_on': published_on}}
    for source in sources:
        if source.verified_at and safe_source_url(source.source_url):
            verified[source_key(source.source_url)] = {
                'verified_at': source.verified_at.isoformat(),
                'published_on': source.published_on.isoformat() if source.published_on else None,
            }
    values = {'summary': public_text(summary), **{k: profile[k] for k in ('direction', 'location', 'achievements')},
              **profile['recruitment']}
    if not details:  # Existing manually maintained records remain usable.
        values.update({k: public_text(v) for k, v in (legacy or {}).items() if v})
        profile['hasRecruitmentSource'] = bool(values.get('roles') or values.get('eligibility'))
        profile['recruitment'] = {k: values[k] for k in RECRUITMENT_KEYS if values.get(k)}
    active = has_recruitment_opportunity({'details': profile}) and not closed
    links, blocks, facts = {}, [], {}
    grouped = {}
    for field, value in values.items():
        if not value:
            continue
        candidates = profile['fieldLinks'].get(field) or (
            profile['fieldLinks'].get('recruitment') if field in RECRUITMENT_KEYS else None)
        candidates = candidates or [{'label': '官方说明', 'url': primary_url}]
        approved = [link for link in candidates if safe_source_url(link['url'])
                    and verified.get(source_key(link['url']), {}).get('verified_at')]
        if not approved:
            continue
        facts[field] = value
        links[field] = approved
        # One piece per section/source; retain field identity and precise source.
        section = 'recruitment' if field in RECRUITMENT_KEYS else 'achievements' if field == 'achievements' else 'introduction'
        url = approved[0]['url']
        group = grouped.setdefault((section, url), {'fields': [], 'lines': []})
        group['fields'].append(field)
        group['lines'].append(f'{LABELS[field]}：{value}')
    for (section, url), group in grouped.items():
        text = '学校／单位：' + public_text(institution) + '\n' + '\n'.join(group['lines'])
        if section == 'recruitment' and not active:
            text += '\n招募状态：历史或已结束'
        blocks.append({'section': section, 'fields': group['fields'], 'text': text,
                       'url': url, **verified[source_key(url)]})
    # An explicit join page without extracted conditions is a reading entry only.
    for field, candidates in profile['fieldLinks'].items():
        if field not in links:
            links[field] = [link for link in candidates if safe_source_url(link['url'])
                            and verified.get(source_key(link['url']), {}).get('verified_at')]
    if (profile['hasRecruitmentSource'] and not any(b['section'] == 'recruitment' for b in blocks)
            and links.get('recruitment')):
        entry = links['recruitment'][0]
        blocks.append({'section': 'recruitment', 'fields': ['recruitment'], 'url': entry['url'],
                       'text': '招募入口：' + entry['label'] + '\n此来源仅提供入口，没有已整理的招募对象或申请条件。',
                       **verified[source_key(entry['url'])]})
    verified_recruitment = profile['hasRecruitmentSource'] and any(b['section'] == 'recruitment' for b in blocks)
    payload = {'institution': public_text(institution), 'facts': facts, 'field_links': links,
               'evidence_blocks': blocks, 'has_recruitment_source': verified_recruitment,
               'recruitment_active': active and verified_recruitment}
    payload['facts_version'] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return payload
