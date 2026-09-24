"""检查输入、输出结构和引文；不能替代来源核实与人工语义判断。"""

import re
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from .exceptions import AIInputError, AIValidationError

NOTICE_FIELDS = ('title', 'organizer', 'eligibility', 'registration_deadline', 'submission_deadline')
DATE_FIELDS = ('registration_deadline', 'submission_deadline')
MAX_INPUT_CHARACTERS = 20000


def _text(value, maximum):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def _keys(value, expected):
    return isinstance(value, dict) and set(value) == set(expected)


def _source_url(value):
    if not _text(value, 2048):
        raise AIInputError('来源链接必须是有效的 HTTP 或 HTTPS 地址。')
    try:
        URLValidator(schemes=['http', 'https'])(value)
    except ValidationError:
        raise AIInputError('来源链接必须是有效的 HTTP 或 HTTPS 地址。') from None


def validate_notice_input(source_text, source_url):
    if not _text(source_text, MAX_INPUT_CHARACTERS):
        raise AIInputError('通知正文不能为空，且不能超过 20000 字符。')
    _source_url(source_url)


def validate_newsletter_input(items):
    if not isinstance(items, list) or not 1 <= len(items) <= 10:
        raise AIInputError('快讯输入需包含 1 至 10 条资讯。')
    seen = set()
    total = 0
    for item in items:
        if not _keys(item, ('id', 'title', 'source_url', 'content')):
            raise AIInputError('资讯需包含 id、title、source_url、content 四个字段。')
        if not _text(item['id'], 128) or item['id'] in seen:
            raise AIInputError('资讯 id 必须是非空且不重复的字符串。')
        if not _text(item['title'], 300) or not _text(item['content'], MAX_INPUT_CHARACTERS):
            raise AIInputError('资讯标题或正文为空，或超过允许长度。')
        _source_url(item['source_url'])
        seen.add(item['id'])
        total += len(item['title']) + len(item['content'])
    if total > MAX_INPUT_CHARACTERS:
        raise AIInputError('快讯输入的标题和正文合计不能超过 20000 字符。')


def _date_supported(value, evidence):
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    patterns = (
        r'(?<![0-9])([0-9]{4})年\s*([0-9]{1,2})月\s*([0-9]{1,2})日',
        r'(?<![0-9])([0-9]{4})([-/])([0-9]{1,2})\2([0-9]{1,2})(?![0-9])',
    )
    for index, pattern in enumerate(patterns):
        for match in re.finditer(pattern, evidence):
            groups = match.groups()
            numbers = groups if index == 0 else (groups[0], groups[2], groups[3])
            if tuple(map(int, numbers)) == (parsed.year, parsed.month, parsed.day):
                return True
    return False


def validate_notice_result(payload, source_text, source_url):
    if not _keys(payload, NOTICE_FIELDS):
        raise AIValidationError('通知提取结果的字段不符合约定。')
    fields = {}
    missing = []
    for name in NOTICE_FIELDS:
        entry = payload[name]
        if not _keys(entry, ('value', 'evidence')):
            raise AIValidationError('提取字段必须包含 value 和 evidence。')
        value, evidence = entry['value'], entry['evidence']
        if value is None and evidence is None:
            missing.append(name)
        else:
            if not _text(value, 2000) or not _text(evidence, 2000) or evidence not in source_text:
                raise AIValidationError('提取结果缺少有效值或可定位的原文引文。')
            if name in DATE_FIELDS:
                if not _date_supported(value, evidence):
                    raise AIValidationError('截止日期格式无效，或引文不包含相同的完整日期。')
            elif value not in evidence:
                raise AIValidationError('提取文本必须是对应引文中的原文片段。')
        fields[name] = {'value': value, 'evidence': evidence}
    return {'source_url': source_url, 'fields': fields,
            'missing_fields': missing, 'requires_review': True}


def validate_newsletter_result(payload, items):
    if not _keys(payload, ('title', 'items')) or not _text(payload['title'], 200):
        raise AIValidationError('快讯结果需包含有效标题和条目列表。')
    entries = payload['items']
    if not isinstance(entries, list) or len(entries) != len(items):
        raise AIValidationError('快讯条目数量必须与输入资讯一致。')
    sources = {item['id']: item for item in items}
    seen = set()
    result = []
    for entry in entries:
        if not _keys(entry, ('source_id', 'summary', 'evidence')):
            raise AIValidationError('快讯条目字段不符合约定。')
        source_id = entry['source_id']
        if not isinstance(source_id, str) or source_id not in sources or source_id in seen:
            raise AIValidationError('快讯引用了未知或重复的资讯。')
        source = sources[source_id]
        if not _text(entry['summary'], 300) or not _text(entry['evidence'], 2000):
            raise AIValidationError('快讯摘要或引文为空，或超过允许长度。')
        if entry['evidence'] not in source['content']:
            raise AIValidationError('快讯引文不在对应资讯正文中。')
        seen.add(source_id)
        result.append({**entry, 'title': source['title'], 'source_url': source['source_url']})
    return {'title': payload['title'], 'items': result, 'requires_review': True}
