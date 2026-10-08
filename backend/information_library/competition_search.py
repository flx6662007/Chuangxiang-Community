"""Competition retrieval, eligibility matching and evidence-backed explanations.

The core accepts a JSON corpus without Django. Only the default corpus adapter
reads the database; no HTTP requests or model calls are made by keyword search.
"""

from copy import deepcopy
from functools import lru_cache
from datetime import date, datetime
import hashlib
import json
import os
import re
import unicodedata
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .semantic import DEFAULT_THRESHOLD, SemanticError, load_index


@lru_cache(maxsize=2)
def _runtime_index(path, modified_ns, size, model_path, revision):
    # Search still validates current document fingerprints on every request.
    return load_index(path)


FIELD_NAMES = (
    'eligibility', 'education', 'grades', 'majors', 'participation_type', 'organizer', 'tracks', 'registration_method',
    'team_size_min', 'team_size_max', 'registration_start', 'registration_deadline',
    'submission_deadline', 'registration_url', 'registration_status', 'status_as_of',
    'registration_deadline_at', 'event_completed_on',
)
FILTER_NAMES = {
    'education', 'grade', 'major', 'category', 'level', 'participation_type',
    'team_size', 'registration_status', 'deadline_from', 'deadline_to',
    'catalog_codes', 'code', 'edition',
}
TOPICS = {
    '人工智能': ('人工智能', '机器学习', '深度学习', 'ai'),
    '机器人': ('机器人', '智能机器人', '智能制造'),
    '程序设计': ('程序设计', '编程', 'coding', '算法竞赛'),
    '数学建模': ('数学建模', '数模'),
    '设计': ('设计', '创意', '艺术设计'),
    '创新创业': ('创新创业', '创业', '商业计划'),
    '科研': ('科研', '科学研究', '研究项目'),
}
EDUCATION = {
    '本科': 'undergraduate', '本科生': 'undergraduate', 'undergraduate': 'undergraduate',
    '研究生': 'postgraduate', 'postgraduate': 'postgraduate',
    '硕士': 'master', '硕士生': 'master', 'master': 'master',
    '博士': 'doctorate', '博士生': 'doctorate', 'doctorate': 'doctorate',
    '专科': 'college', '专科生': 'college', 'college': 'college',
    '大专': 'college', '高中': 'high_school', '高中生': 'high_school', 'high_school': 'high_school',
    '硕士研究生': 'master', '博士研究生': 'doctorate',
}
LEVELS = {'unknown', 'international', 'national', 'provincial', 'municipal', 'university', 'college', 'other'}
ALL_VALUES = {'all', 'any', '不限', '不限专业', '全专业', '不限年级', '全年级'}
STOP_PHRASES = (
    '帮我找', '推荐一些', '推荐一个', '推荐', '我想参加', '我想找', '想找', '寻找',
    '适合', '可以参加', '能参加', '参赛', '相关', '比赛', '竞赛', '赛事', '有关',
    '我是', '学生', '我会', '希望', '最好', '优先', '喜欢', '感兴趣', '必须', '只要',
    '仅限', '只找', '近期', '最近', '现在', '目前', '还能报名', '可报名', '可以报名',
    '报名开放', '报名中', '未截止', '组队', '团队', '个人', '独立参加', '不限',
    '大一', '大二', '大三', '大四', '大五', '本科生', '研究生', '博士生', '硕士生',
    '本科', '专科', '年级', '专业', '一个', '一些',
)


def _normalize(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(value or '')).casefold())


def _contains(text, term):
    needle = _normalize(term)
    if not needle:
        return False
    if needle.isascii():
        return bool(re.search(r'(?<![a-z])' + re.escape(needle) + r'(?![a-z])', text))
    return needle in text


def _day(value, *, name='date'):
    if isinstance(value, datetime):
        return value.astimezone(ZoneInfo('Asia/Shanghai')).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError(f'{name} 必须使用 YYYY-MM-DD。')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f'{name} 必须使用有效日期。') from None


def _optional_day(value):
    try:
        return _day(value)
    except (TypeError, ValueError):
        return None


def _values(value):
    if value is None or value == '':
        return []
    return value if isinstance(value, list) else [value]


def _education(value):
    return EDUCATION.get(_normalize(value), _normalize(value))


def _grades(value):
    normalized = _normalize(value)
    if normalized in ALL_VALUES:
        return set(range(1, 7))
    names = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6}
    match = re.search(r'(?:大|本科)?([一二三四五六1-6])(?:年级)?', normalized)
    if not match:
        return set()
    number = names.get(match[1], int(match[1]) if match[1].isdigit() else 0)
    if '以上' in normalized or '及高' in normalized:
        return set(range(number, 7))
    if '以下' in normalized:
        return set(range(1, number + 1))
    end = re.search(r'(?:至|到|-|~)(?:大)?([一二三四五六1-6])', normalized)
    if end:
        last = names.get(end[1], int(end[1]) if end[1].isdigit() else 0)
        return set(range(number, last + 1))
    return {number}


def _safe_url(value):
    if not isinstance(value, str) or re.search(r'[\s\x00-\x1f]', value):
        return ''
    try:
        url = urlsplit(value)
        return value if url.scheme in {'http', 'https'} and url.hostname and not url.username and not url.password else ''
    except ValueError:
        return ''


def _sources(record, ids=None):
    allowed = set(ids) if ids is not None else None
    result = []
    for source in record.get('sources', []):
        if (allowed is not None and source.get('id') not in allowed) or not _safe_url(source.get('url')):
            continue
        result.append({key: source.get(key) for key in ('id', 'url', 'title', 'quote', 'locator', 'verified_at')})
    return result


def _field_evidence(record, field):
    return [source['id'] for source in _sources(record, record.get('field_evidence', {}).get(field, []))]


def _registration_status(fields, today):
    start, end = _optional_day(fields.get('registration_start')), _optional_day(fields.get('registration_deadline'))
    if end and end < today:
        return 'closed'
    if start and start > today:
        return 'upcoming'
    if start and end and start <= today <= end:
        return 'open'
    # A dated official status is usable on its stated date; a deadline alone is not an opening date.
    if fields.get('registration_status') in {'open', 'closed', 'upcoming'} and _optional_day(fields.get('status_as_of')) == today:
        return fields['registration_status']
    return 'unknown'


def _matches(record, key, expected, today):
    fields = record.get('fields', {})
    expected_values = _values(expected)
    if key in {'education', 'major', 'grade'}:
        field = {'education': 'education', 'major': 'majors', 'grade': 'grades'}[key]
        actual = _values(fields.get(field))
        if not actual:
            return False, []
        normalized = {_normalize(item) for item in actual}
        if normalized & ALL_VALUES:
            matches = True
        elif key == 'grade':
            actual_grades = set().union(*(_grades(item) for item in actual))
            matches = any(_grades(item) <= actual_grades and bool(_grades(item)) for item in expected_values)
        elif key == 'education':
            actual_education = {_education(item) for item in actual}
            matches = any(_education(item) in actual_education
                          or (_education(item) in {'master', 'doctorate'} and 'postgraduate' in actual_education)
                          for item in expected_values)
        else:
            matches = any(_normalize(item).removesuffix('专业') in {v.removesuffix('专业') for v in normalized}
                          for item in expected_values)
        evidence = _field_evidence(record, field)
        return matches and bool(evidence), evidence
    if key == 'participation_type':
        actual = fields.get(key)
        evidence = _field_evidence(record, key)
        return actual in {expected, 'both'} and actual not in {'', None, 'unknown'} and bool(evidence), evidence
    if key == 'team_size':
        minimum, maximum = fields.get('team_size_min'), fields.get('team_size_max')
        low_evidence, high_evidence = _field_evidence(record, 'team_size_min'), _field_evidence(record, 'team_size_max')
        return (type(minimum) is int and type(maximum) is int and minimum <= expected <= maximum
                and bool(low_evidence) and bool(high_evidence)), low_evidence + high_evidence
    if key == 'registration_status':
        if _registration_status(fields, today) != expected:
            return False, []
        start, end = _optional_day(fields.get('registration_start')), _optional_day(fields.get('registration_deadline'))
        alternatives = []
        if expected == 'upcoming' and start and start > today:
            alternatives.append(('registration_start',))
        elif expected == 'closed' and end and end < today:
            alternatives.append(('registration_deadline',))
        elif expected == 'open' and start and end and start <= today <= end:
            alternatives.append(('registration_start', 'registration_deadline'))
        if fields.get('registration_status') == expected and _optional_day(fields.get('status_as_of')) == today:
            alternatives.append(('registration_status', 'status_as_of'))
        for evidence_fields in alternatives:
            supported = [_field_evidence(record, field) for field in evidence_fields]
            if all(supported):
                return True, sum(supported, [])
        return False, []
    if key in {'deadline_from', 'deadline_to'}:
        deadline = _optional_day(fields.get('registration_deadline'))
        bound = _day(expected)
        evidence = _field_evidence(record, 'registration_deadline')
        return bool(deadline and evidence and (deadline >= bound if key == 'deadline_from' else deadline <= bound)), evidence
    if key == 'catalog_codes':
        actual_codes = _values(record.get('catalog_codes') or record.get('catalog_code'))
        return bool({str(item) for item in actual_codes} & {str(item) for item in expected_values}), []
    actual = record.get(key)
    if key == 'category' and isinstance(actual, dict):
        actual = [actual.get('code'), actual.get('name')]
    return bool(actual) and bool({_normalize(item) for item in _values(actual)}
                                & {_normalize(item) for item in expected_values}), _field_evidence(record, key)


def _condition_state(record, key, expected, today):
    matched, evidence = _matches(record, key, expected, today)
    if matched:
        return 'matched'
    fields = record.get('fields', {})
    if key in {'education', 'grade', 'major'}:
        field = {'education': 'education', 'grade': 'grades', 'major': 'majors'}[key]
        actual = _values(fields.get(field))
        known = bool(actual and _field_evidence(record, field))
        if key == 'grade':
            known = known and any(_grades(item) for item in actual)
    elif key == 'participation_type':
        known = bool(fields.get(key) and _field_evidence(record, key))
    elif key == 'team_size':
        known = all(fields.get(name) is not None and _field_evidence(record, name)
                    for name in ('team_size_min', 'team_size_max'))
    elif key == 'registration_status':
        status = _registration_status(fields, today)
        known = status != 'unknown' and _matches(record, key, status, today)[0]
    elif key in {'deadline_from', 'deadline_to'}:
        known = bool(_optional_day(fields.get('registration_deadline')) and _field_evidence(record, 'registration_deadline'))
    elif key == 'catalog_codes':
        known = bool(record.get('catalog_codes') or record.get('catalog_code'))
    elif key == 'category':
        category = _public_category(record)
        known = bool(category and (category.get('code') or category.get('name')))
    else:
        known = bool(record.get(key)) and record.get(key) != 'unknown'
    return 'unmatched' if known else 'unknown'


def _empty_result(query, filters, records, candidates, today):
    labels = {'education': '学历', 'grade': '年级', 'major': '专业', 'category': '赛事类别',
              'level': '赛事范围', 'participation_type': '参赛形式', 'team_size': '团队人数',
              'registration_status': '报名状态', 'deadline_from': '报名截止不早于',
              'deadline_to': '报名截止不晚于', 'catalog_codes': '赛事目录', 'code': '赛事编号', 'edition': '届次'}
    values = {'team': '团队参赛', 'individual': '个人参赛', 'both': '个人或团队参赛',
              'open': '报名正在进行', 'closed': '报名已结束', 'upcoming': '报名尚未开始',
              'undergraduate': '本科', 'college': '专科', 'postgraduate': '研究生',
              'master': '硕士', 'doctorate': '博士', 'high_school': '高中'}
    conditions = []
    for name, value in filters.items():
        counts = {'matched': 0, 'unmatched': 0, 'unknown': 0}
        for row in records.values():
            counts[_condition_state(row, name, value, today)] += 1
        display = '、'.join(values.get(str(item), str(item)) for item in _values(value))
        conditions.append({'field': name, 'label': labels[name], 'value': deepcopy(value),
                           'display_value': display, **counts})
    if not records:
        code, message = 'empty_corpus', '目前没有可检索的赛事资料。'
    elif filters and not candidates:
        joined = '；'.join(f"{item['label']}：{item['display_value']}" for item in conditions)
        code, message = 'no_condition_match', f'没有找到同时满足以下条件的赛事：{joined}。'
    else:
        code, message = 'no_topic_match', f'没有找到与“{query}”匹配的赛事。'
    return {'code': code, 'message': message, 'conditions': conditions}


def _validate_constraints(constraints):
    if constraints is None:
        return {}
    if not isinstance(constraints, dict) or set(constraints) - FILTER_NAMES:
        raise ValueError('筛选条件包含不支持的字段。')
    for key, value in constraints.items():
        if key == 'team_size':
            if type(value) is not int or not 1 <= value <= 1000:
                raise ValueError('team_size 必须是 1 至 1000 的整数。')
        elif key == 'participation_type':
            if value not in ('team', 'individual', 'both'):
                raise ValueError('participation_type 必须是 team、individual 或 both。')
        elif key == 'registration_status':
            if value not in ('open', 'closed', 'upcoming'):
                raise ValueError('registration_status 必须是 open、closed 或 upcoming。')
        elif key in {'deadline_from', 'deadline_to'}:
            _day(value, name=key)
        elif not _values(value) or any(not isinstance(item, str) or not item.strip() or len(item) > 200 for item in _values(value)):
            raise ValueError(f'{key} 必须是非空文本或文本列表。')
        elif key == 'education' and any(_education(item) not in set(EDUCATION.values()) for item in _values(value)):
            raise ValueError('education 须为本科、专科、研究生、硕士、博士或高中。')
        elif key == 'grade' and any(not re.fullmatch(r'(?:大|本科)?[一二三四五六1-6](?:年级)?(?:及以上|以上|以下|(?:至|到|-|~)(?:大)?[一二三四五六1-6])?', item) for item in _values(value)):
            raise ValueError('grade 须为明确年级或年级范围。')
        elif key == 'level' and any(item not in LEVELS - {'unknown'} for item in _values(value)):
            raise ValueError('level 须为明确的赛事范围编码。')
    if 'deadline_from' in constraints and 'deadline_to' in constraints and _day(constraints['deadline_from']) > _day(constraints['deadline_to']):
        raise ValueError('截止日期范围的开始不能晚于结束。')
    return deepcopy(constraints)


def interpret_query(query):
    """Conservative local interpretation; callers may supply model-parsed filters separately."""
    grade = re.search(r'大[一二三四五六]', query)
    major = re.search(r'([\u4e00-\u9fff]{2,12})专业', query)
    major_text = major[1] if major else None
    if major_text:
        major_text = re.sub(r'^(?:(?:我是|我学|就读|来自|一名|在读)|大[一二三四五六])+', '', major_text)
    interests = [name for name, aliases in TOPICS.items() if any(
        re.search(r'(?<![a-z])' + re.escape(alias) + r'(?![a-z])', query, re.I) if alias.isascii()
        else alias in query for alias in aliases)]
    participation = 'team' if re.search(r'组队|团队', query) else ('individual' if re.search(r'个人|独立参加', query) else None)
    registration = 'open' if re.search(r'可报名|可以报名|还能报名|报名开放|报名中', query) else None
    interpretation = {
        'major': major_text, 'grade': grade[0] if grade else None, 'interests': interests,
        'participationType': participation, 'registrationStatus': registration,
    }
    filters, preferences = {}, {}
    if registration:
        filters['registration_status'] = registration
    for key, value in [('major', major_text), ('grade', interpretation['grade']), ('participation_type', participation)]:
        if value:
            preferences[key] = value
    if participation and re.search(
        r'(?:必须|只要|仅限|只找)(?:可以|支持|能够|能|是|为|参加|能参加|支持我)?(?:组队|团队|个人|独立参加)', query,
    ):
        filters['participation_type'] = participation
    return interpretation, filters, preferences


def _terms(query, interpretation):
    text = query.casefold()
    for aliases in TOPICS.values():
        for alias in aliases:
            if alias.isascii():
                continue
            text = text.replace(alias, ' ' + alias + ' ')
    for phrase in sorted(STOP_PHRASES, key=len, reverse=True):
        text = text.replace(phrase, ' ')
    for value in (interpretation['major'],):
        if value:
            text = text.replace(value, ' ')
    terms = set()
    for word in re.findall(r'[a-z][a-z0-9+#.-]*|[\u4e00-\u9fff]{2,}', text):
        if word.isascii() or len(word) <= 4:
            terms.add(word)
        else:
            terms.update(word[i:i + 2] for i in range(len(word) - 1))
    terms -= {'给我', '参加', '我的', '感兴', '兴趣', '希望', '一下', '哪些', '什么', '还有', '有什', '我想'}
    return terms


def _keyword_score(record, query, terms, interests):
    title = _normalize(record['title'])
    aliases = [_normalize(alias) for alias in record.get('aliases', [])]
    needle = _normalize(query)
    exact = int(bool(needle) and needle in [title, *aliases])
    named = int(any(len(alias) >= 2 and _contains(needle, alias) for alias in [title, *aliases])
                or (len(needle) >= 4 and any(_contains(alias, needle) for alias in [title, *aliases])))
    fields = record.get('fields', {})
    body = '。'.join([record.get('summary', ''), fields.get('eligibility', ''),
                     *[section.get('text', '') for section in record.get('sections', [])
                       if _sources(record, section.get('evidence_ids', []))]])
    if '人工智能' in interests and not re.search(r'规则|使用|允许|禁止|限制|诚信', query):
        # Tool-use policies are searchable as rules, but do not define an AI competition topic.
        clauses = re.split(r'[。！？；;\n]', body)
        body = '。'.join(clause for clause in clauses if not re.search(
            r'(?:禁止|不得|不能|限制).{0,20}(?:AI|人工智能)|(?:AI|人工智能).{0,4}使用.{0,6}(?:另查|规定|限制|规范|政策)',
            clause, re.I,
        ))
    text = _normalize(' '.join([record['title'], *record.get('aliases', []), body]))
    math_topic = any(_contains(value, alias) for value in [title, *aliases] for alias in ('数学建模', '数模')) or _contains(text, '数学建模')

    def matches_term(term):
        if term == '数模' and '数学建模' in interests and not math_topic:
            return False
        return _contains(text, term)

    matched = {term for term in terms if matches_term(term)}
    topic_hits = [next(alias for alias in TOPICS[name] if matches_term(alias))
                  for name in interests if any(matches_term(alias) for alias in TOPICS[name])]
    topic_hits = ['AI' if name == 'ai' else name for name in topic_hits]
    # Long requests need enough shared content to establish a lexical topic.
    # A lone bigram (e.g. an age/grouping term) is not a subject match. Names,
    # known topic aliases and longer title phrases remain useful entry points.
    title_phrase = any(len(term) >= 4 and (_contains(title, term) or any(
        _contains(alias, term) for alias in aliases)) for term in matched)
    if (len(terms) >= 6 and not (exact or named or topic_hits or title_phrase)
            and (len(matched) < 2 or len(matched) / len(terms) < 0.15)):
        return 0.0, exact, set(), []
    score = exact * 1000 + named * 100 + sum(5 if _contains(title, term) or any(_contains(alias, term) for alias in aliases) else 1 for term in matched) + len(topic_hits) * 8
    return float(score), exact, matched, topic_hits


def _reason(record, key, expected, evidence_ids):
    if not evidence_ids:
        return None
    fields = record.get('fields', {})
    labels = {'education': '参赛学历', 'grade': '参赛年级', 'major': '参赛专业', 'category': '赛事类别', 'level': '赛事范围'}
    if key in labels:
        actual = fields.get({'grade': 'grades', 'major': 'majors'}.get(key, key), record.get(key))
        if isinstance(actual, dict):
            actual = actual.get('name', actual.get('code'))
        text = f"{labels[key]}：{'、'.join(map(str, _values(actual)))}"
    elif key == 'participation_type':
        text = {'team': '支持团队参赛', 'individual': '支持个人参赛', 'both': '支持个人或团队参赛'}[fields['participation_type']]
    elif key == 'team_size':
        text = f"参赛团队人数为 {fields['team_size_min']}—{fields['team_size_max']} 人，符合 {expected} 人组队需求"
    elif key == 'registration_status':
        text = {'open': '报名正在进行', 'closed': '报名已结束', 'upcoming': '报名尚未开始'}[expected]
        if fields.get('registration_deadline'):
            text += f"，截止日期为 {fields['registration_deadline']}"
    elif key in {'deadline_from', 'deadline_to'}:
        text = f"报名截止日期为 {fields['registration_deadline']}"
    else:
        return None
    return {'text': text, 'evidence_ids': list(dict.fromkeys(evidence_ids))}


def _corpus_from_database():
    from curation.retrieval import student_visible_documents
    from competitions.serializers import CompetitionListSerializer
    from competitions.selectors import public_competition_queryset
    records, diagnostics, revisions = [], [], []
    public_competitions = {}
    for document in student_visible_documents().select_related('current_revision').prefetch_related('current_revision__links__competition'):
        revision = document.current_revision
        raw = revision.metadata.get('search_record')
        if not isinstance(raw, dict):
            continue
        sections = raw.get('sections')
        expected_body = ('\n\n'.join(f"## {section['heading']}\n\n{section['text']}" for section in sections)
                         if isinstance(sections, list) and all(isinstance(section, dict)
                         and isinstance(section.get('heading'), str) and isinstance(section.get('text'), str)
                         for section in sections) else None)
        if (expected_body is None or expected_body.replace('\r\n', '\n').strip() != revision.body.replace('\r\n', '\n').strip()
                or raw.get('title') != revision.title or raw.get('edition', '') != revision.edition
                or raw.get('sources', []) != revision.sources):
            diagnostics.append({'code': 'document_search_record_mismatch', 'document_code': document.code,
                                'revision': revision.version})
            continue
        row = deepcopy(raw)
        # These values are authoritative database state, not imported metadata flags.
        row['review_status'] = document.review_status
        row['publication_status'] = 'published'
        linked = {link.competition_id for link in revision.links.all()
                  if link.competition_id and link.competition.publication_status == 'published'}
        row['competition_id'] = next(iter(linked)) if len(linked) == 1 else None
        if row['competition_id']:
            public_competitions.setdefault(row['competition_id'], []).append(row)
        records.append(row)
        revisions.append((str(row['id']), row['content_hash'], revision.version, revision.content_hash))
    # Serialize actual public objects, with the same deadlines and sources as the list API.
    available = set()
    public_rows = public_competition_queryset().filter(pk__in=public_competitions) if public_competitions else ()
    for competition in public_rows:
        card = dict(CompetitionListSerializer(competition).data)
        available.add(competition.pk)
        for row in public_competitions[competition.pk]:
            row['_public_competition'] = card
    for row in records:
        if row['competition_id'] not in available:
            row['competition_id'] = None
    version = hashlib.sha256(json.dumps(sorted(revisions)).encode()).hexdigest()
    return {'schema_version': 1, 'version': version,
            'as_of': datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat(), 'records': records,
            'diagnostics': diagnostics}


def _validate_corpus(corpus):
    if (not isinstance(corpus, dict) or type(corpus.get('schema_version')) is not int or corpus['schema_version'] != 1
            or not isinstance(corpus.get('records'), list) or not isinstance(corpus.get('version'), str) or not corpus['version']):
        raise ValueError('语料格式或版本无效。')
    seen = set()
    for record in corpus['records']:
        if (not isinstance(record, dict) or not isinstance(record.get('id'), str) or not record['id']
                or record['id'] in seen or not isinstance(record.get('title'), str) or not record['title'].strip()
                or not isinstance(record.get('content_hash'), str) or not record['content_hash'] or not isinstance(record.get('fields'), dict)):
            raise ValueError('赛事记录编号、标题、字段或内容版本无效。')
        seen.add(record['id'])
        if (record.get('review_status') not in ('draft', 'approved', 'published', 'withdrawn')
                or record.get('publication_status') not in ('draft', 'published', 'withdrawn')
                or not isinstance(record.get('level', 'unknown'), str) or record.get('level', 'unknown') not in LEVELS):
            raise ValueError('赛事审核、发布状态或范围编码无效。')
        for name in ('aliases', 'catalog_codes'):
            value = record.get(name, [])
            if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
                raise ValueError(f'{name} 必须为文本列表。')
        for name in ('summary', 'edition', 'code'):
            if not isinstance(record.get(name, ''), str):
                raise ValueError(f'{name} 必须为文本。')
        if record.get('category') is not None and not isinstance(record['category'], (str, dict)):
            raise ValueError('category 必须为分类文本或对象。')
        if isinstance(record.get('category'), dict):
            category = record['category']
            if (any(key in category and not isinstance(category[key], str) for key in ('code', 'name'))
                    or ('id' in category and (type(category['id']) is not int or category['id'] <= 0))):
                raise ValueError('分类编号、编码或名称无效。')
        evidence = record.get('field_evidence', {})
        if not isinstance(evidence, dict) or any(not isinstance(ids, list) or any(not isinstance(key, str) for key in ids) for ids in evidence.values()):
            raise ValueError('字段证据须为来源编号列表。')
        sources = record.get('sources', [])
        if not isinstance(sources, list):
            raise ValueError('sources 必须为来源列表。')
        source_ids = set()
        for source in sources:
            if (not isinstance(source, dict) or not isinstance(source.get('id'), str) or not source['id']
                    or source['id'] in source_ids or not isinstance(source.get('url'), str)
                    or any(source.get(key) is not None and not isinstance(source[key], str)
                           for key in ('title', 'quote', 'locator', 'verified_at'))):
                raise ValueError('来源编号、链接或引用字段无效。')
            source_ids.add(source['id'])
        sections = record.get('sections', [])
        if not isinstance(sections, list):
            raise ValueError('sections 必须为正文段落列表。')
        section_ids = set()
        for section in sections:
            if (not isinstance(section, dict) or not isinstance(section.get('id'), str) or not section['id']
                    or section['id'] in section_ids or not isinstance(section.get('heading'), str)
                    or not isinstance(section.get('text'), str) or not isinstance(section.get('evidence_ids', []), list)
                    or any(not isinstance(key, str) for key in section.get('evidence_ids', []))):
                raise ValueError('正文段落编号、文字或来源编号无效。')
            section_ids.add(section['id'])
        fields = record['fields']
        for name in FIELD_NAMES:
            value = fields.get(name)
            if value is None:
                continue
            if name in {'education', 'grades', 'majors'}:
                if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
                    raise ValueError(f'{name} 必须为文本列表。')
            elif name in {'team_size_min', 'team_size_max'}:
                if type(value) is not int or not 1 <= value <= 1000:
                    raise ValueError(f'{name} 必须为正整数。')
            elif not isinstance(value, str):
                raise ValueError(f'{name} 必须为文本。')
            elif name in {'registration_start', 'registration_deadline', 'submission_deadline', 'status_as_of', 'event_completed_on'} and value:
                _day(value, name=name)
            elif name == 'registration_deadline_at' and value:
                if datetime.fromisoformat(value).tzinfo is None:
                    raise ValueError('报名截止时刻需要时区。')
        if fields.get('participation_type') not in (None, '', 'individual', 'team', 'both'):
            raise ValueError('参赛形式编码无效。')
        if fields.get('registration_status') not in (None, '', 'open', 'closed', 'upcoming'):
            raise ValueError('报名状态编码无效。')
        low, high = fields.get('team_size_min'), fields.get('team_size_max')
        if low is not None and high is not None and low > high:
            raise ValueError('团队人数下限不能大于上限。')
        start, end = _optional_day(fields.get('registration_start')), _optional_day(fields.get('registration_deadline'))
        if start and end and start > end:
            raise ValueError('报名开始日期不能晚于截止日期。')


def database_corpus():
    """Return the current approved, publicly available database corpus for indexing."""
    return _corpus_from_database()


def _public_fields(record):
    fields = record.get('fields', {})
    return {name: deepcopy(fields.get(name, [] if name in {'education', 'grades', 'majors'} else None)) for name in FIELD_NAMES}


def _public_category(record):
    category = record.get('category')
    if isinstance(category, str):
        return {'code': category, 'name': category} if category.strip() else None
    if isinstance(category, dict):
        return {key: category[key] for key in ('id', 'code', 'name') if key in category}
    return None


def _card(record, today):
    identifier = record.get('competition_id')
    if type(identifier) is not int or not 0 < identifier <= 9007199254740991:
        return None
    if '_public_competition' in record:
        stored = record['_public_competition']
        names = ('id', 'code', 'title', 'edition', 'summary', 'level', 'organizer', 'eligibility',
                 'participation_type', 'team_size_min', 'team_size_max', 'registration_deadline',
                 'registration_deadline_at', 'registration_deadline_timezone', 'submission_deadline',
                 'submission_deadline_at', 'submission_deadline_timezone', 'published_at', 'updated_at',
                 'last_verified_at', 'is_recruitment_open', 'deadline_kind', 'deadline_status', 'deadline_status_label')
        card = {key: deepcopy(stored.get(key)) for key in names}
        card['category'] = _public_category(stored)
        card['tags'] = [{key: tag[key] for key in ('id', 'code', 'name') if key in tag} for tag in stored.get('tags', [])]
        source = stored.get('primary_source')
        card['primary_source'] = ({key: source.get(key) for key in
                                  ('id', 'source_type', 'source_name', 'source_url', 'source_published_on', 'source_updated_on', 'last_verified_at')}
                                 if isinstance(source, dict) else None)
        return card
    fields = _public_fields(record)
    deadline = _optional_day(fields.get('registration_deadline'))
    submission = _optional_day(fields.get('submission_deadline'))
    kind = 'registration' if deadline else ('submission' if submission else 'unknown')
    selected = deadline or submission
    status = 'closed' if selected and selected < today else ('open' if selected else 'unknown')
    source = next(iter(_sources(record)), None)
    category = _public_category(record)
    return {
        'id': identifier, 'code': record.get('code'), 'title': record['title'], 'edition': record.get('edition', ''),
        'summary': record.get('summary', ''), 'category': category, 'tags': [],
        'level': record.get('level') or 'unknown', 'organizer': fields.get('organizer') or '',
        'eligibility': fields.get('eligibility') or '',
        'participation_type': fields.get('participation_type') or 'unknown',
        'team_size_min': fields.get('team_size_min'), 'team_size_max': fields.get('team_size_max'),
        'registration_deadline': fields.get('registration_deadline'), 'registration_deadline_at': None,
        'registration_deadline_timezone': '', 'submission_deadline': fields.get('submission_deadline'),
        'submission_deadline_at': None, 'submission_deadline_timezone': '',
        'deadline_kind': kind, 'deadline_status': status,
        'deadline_status_label': ('报名' if kind == 'registration' else '作品提交') + ('已截止' if status == 'closed' else '尚未截止') if selected else '报名时间信息不足',
        'is_recruitment_open': False, 'published_at': None, 'updated_at': None,
        'last_verified_at': source.get('verified_at') if source else None,
        'primary_source': {'source_name': source['title'], 'source_url': source['url'], 'source_published_on': None} if source else None,
    }


def search_competitions(query, *, filters=None, preferences=None, as_of=None, mode='hybrid', limit=5, corpus=None, index=None):
    if not isinstance(query, str) or len(query) > 500:
        raise ValueError('query 必须是不超过 500 字符的文本。')
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError('limit 必须为 1 至 50。')
    if not isinstance(mode, str) or mode not in {'keyword', 'semantic', 'hybrid'}:
        raise ValueError('mode 必须为 keyword、semantic 或 hybrid。')
    query = query.strip()
    interpretation, inferred_filters, inferred_preferences = interpret_query(query)
    filters = {**inferred_filters, **_validate_constraints(filters)}
    preferences = {**inferred_preferences, **_validate_constraints(preferences)}
    if not query and not filters and not preferences:
        raise ValueError('请输入参赛需求或筛选条件。')
    today = _day(as_of, name='as_of') if as_of is not None else datetime.now(ZoneInfo('Asia/Shanghai')).date()
    corpus = _corpus_from_database() if corpus is None else corpus
    _validate_corpus(corpus)
    records = {row['id']: row for row in corpus['records'] if row.get('review_status') in ('approved', 'published')
               and row.get('publication_status') == 'published' and _sources(row)}
    candidates, matched_constraints = {}, {}
    for key, row in records.items():
        matches = [(name, value, *_matches(row, name, value, today)) for name, value in filters.items()]
        if all(match[2] for match in matches):
            candidates[key] = row
            matched_constraints[key] = [(name, value, evidence) for name, value, _, evidence in matches]
    terms = _terms(query, interpretation)
    keyword, keyword_details, preference_scores = [], {}, {}
    for key, row in candidates.items():
        score, exact, matched, topics = _keyword_score(row, query, terms, interpretation['interests'])
        preferred = [(name, value, *_matches(row, name, value, today)) for name, value in preferences.items()]
        preference_scores[key] = sum(int(ok) for _, _, ok, _ in preferred)
        matched_constraints[key] += [(name, value, evidence) for name, value, ok, evidence in preferred if ok]
        keyword_details[key] = {'exact': exact, 'matched': matched, 'topics': topics}
        if score > 0 or not terms or not query:
            keyword.append((key, score + preference_scores[key] * 0.1))
    keyword.sort(key=lambda item: (-item[1], item[0]))
    semantic, semantic_hits, warnings = [], {}, []
    used = mode
    if mode != 'keyword' and query:
        try:
            if index is None:
                path = os.getenv('COMPETITION_SEMANTIC_INDEX')
                if not path:
                    raise SemanticError('semantic_index_unconfigured')
                stat = os.stat(path)
                index = _runtime_index(os.path.abspath(path), stat.st_mtime_ns, stat.st_size,
                                       os.getenv('COMPETITION_EMBEDDING_MODEL_PATH', ''),
                                       os.getenv('COMPETITION_EMBEDDING_REVISION', ''))
            elif isinstance(index, (str, os.PathLike)):
                index = load_index(index)
            if not hasattr(index, 'search') or not callable(index.search):
                raise SemanticError('semantic_index_invalid')
            threshold = float(os.getenv('COMPETITION_SEMANTIC_THRESHOLD', str(DEFAULT_THRESHOLD)))
            semantic_hits = {hit['record_id']: hit for hit in index.search(query, corpus, threshold=threshold)
                             if hit['record_id'] in candidates}
            semantic = [(key, hit['score']) for key, hit in semantic_hits.items()]
            semantic.sort(key=lambda item: (-item[1], item[0]))
        except (SemanticError, OSError, ValueError) as error:
            used = 'keyword'
            code = str(error) if isinstance(error, SemanticError) else 'semantic_configuration_invalid'
            warnings.append({'code': code, 'message': '本次使用关键词检索。'})
    elif not query:
        used = 'keyword'
    if used == 'keyword':
        ranking = keyword
    elif used == 'semantic':
        ranking = semantic
    else:
        scores = {}
        for ranking_list in (keyword, semantic):
            for rank, (key, _) in enumerate(ranking_list, start=1):
                scores[key] = scores.get(key, 0) + 1 / (60 + rank)
        ranking = sorted(scores.items(), key=lambda item: (-keyword_details[item[0]]['exact'], -item[1],
                                                          -preference_scores[item[0]], item[0]))
    hits, results, knowledge, seen_cards = [], [], [], set()
    for key, score in ranking[:limit]:
        row = candidates[key]
        reasons = []
        for name, value, evidence_ids in matched_constraints[key]:
            reason = _reason(row, name, value, evidence_ids)
            if reason and reason not in reasons:
                reasons.append(reason)
        semantic_hit = semantic_hits.get(key, {}) if used != 'keyword' else {}
        retrieval_ids = semantic_hit.get('evidence_ids', [])
        supported, passage_candidates = None, []
        public_sections = [section for section in row.get('sections', [])
                           if _sources(row, section.get('evidence_ids', []))]
        if not row.get('sections') and row.get('summary'):
            public_sections = [{'id': 'summary', 'heading': '赛事介绍', 'text': row['summary'],
                                'evidence_ids': [source['id'] for source in _sources(row)]}]
        if semantic_hit:
            supported = next((section for section in public_sections
                              if section['id'] == semantic_hit.get('section_id')), None)
            if supported:
                passage_candidates = [supported]
        else:
            matched_words = set(keyword_details[key]['matched']) | set(keyword_details[key]['topics'])
            relevant_sections = sorted(public_sections, reverse=True, key=lambda section: sum(
                _contains(_normalize(section.get('text')), term) for term in matched_words))
            matching_sections = [section for section in relevant_sections if any(
                _contains(_normalize(section.get('text')), term) for term in matched_words)]
            if matching_sections:
                supported = matching_sections[0]
                passage_candidates = matching_sections
                retrieval_ids = list(dict.fromkeys(source_id for section in matching_sections
                                                  for source_id in section.get('evidence_ids', [])))
        if not retrieval_ids:
            retrieval_ids = [source['id'] for source in _sources(row)]
        else:
            retrieval_ids = [source['id'] for source in _sources(row, retrieval_ids)]
        if not passage_candidates:
            passage_candidates = [section for section in public_sections
                                  if set(section.get('evidence_ids', [])) & set(retrieval_ids)]
        valid_source_ids = {source['id'] for source in _sources(row)}
        passages = [{'id': section['id'], 'heading': section['heading'], 'text': section['text'],
                     'evidence_ids': [source_id for source_id in section.get('evidence_ids', []) if source_id in valid_source_ids]}
                    for section in passage_candidates if any(source_id in valid_source_ids for source_id in section.get('evidence_ids', []))][:3]
        topics = keyword_details[key]['topics']
        if topics:
            topic_sections = [section for section in public_sections if any(
                _contains(_normalize(section['text']), topic) for topic in topics)]
            topic_evidence = list(dict.fromkeys(source_id for section in topic_sections
                                                for source_id in section.get('evidence_ids', [])
                                                if source_id in valid_source_ids))
            reasons.append({'text': f"赛事内容涉及{'、'.join(topics)}",
                            'evidence_ids': topic_evidence or [source['id'] for source in _sources(row)]})
        if not reasons:
            if keyword_details[key]['exact']:
                reason_text = f"与赛事名称“{row['title']}”匹配"
            else:
                excerpt = supported.get('text', '') if supported else ''
                reason_text = (f"{supported['heading']}：{excerpt[:160]}{'…' if len(excerpt) > 160 else ''}"
                               if supported else f"赛事主题：{row['title']}")
            reasons.append({'text': reason_text, 'evidence_ids': retrieval_ids})
        evidence_ids = list(dict.fromkeys([item for reason in reasons for item in reason['evidence_ids']]
                                         + [item for passage in passages for item in passage['evidence_ids']]))
        hit = {
            'record_id': key, 'code': row.get('code'), 'catalog_code': row.get('catalog_code'),
            'catalog_codes': deepcopy(row.get('catalog_codes') or [row.get('catalog_code')]),
            'title': row['title'], 'edition': row.get('edition', ''), 'summary': row.get('summary', ''),
            'category': _public_category(row), 'level': row.get('level'),
            'score': round(float(score), 8), 'match_status': 'matched', 'match_reasons': reasons,
            'evidence': _sources(row, evidence_ids), 'fields': _public_fields(row),
            'content_hash': row['content_hash'], 'passages': passages,
            'condition_checks': [{'field': name, 'role': role, 'value': deepcopy(value),
                                  'state': _condition_state(row, name, value, today)}
                                 for role, constraints in [('filter', filters), ('preference', preferences)]
                                 for name, value in constraints.items()],
        }
        hits.append(hit)
        card = _card(row, today)
        if card:
            if card['id'] not in seen_cards:
                seen_cards.add(card['id'])
                results.append({'record_id': key, 'competition': card,
                                'matchReason': '；'.join(reason['text'] for reason in reasons) + '。',
                                'evidence': hit['evidence'], 'passages': passages, 'content_hash': row['content_hash']})
        else:
            knowledge.append(deepcopy(hit))
    return {'interpretation': interpretation, 'results': results, 'knowledge_results': knowledge,
            'hits': hits, 'mode_used': used, 'warnings': warnings,
            'corpus_version': corpus['version'], 'as_of': today.isoformat(),
            'empty_result': None if hits else _empty_result(query, filters, records, candidates, today)}
