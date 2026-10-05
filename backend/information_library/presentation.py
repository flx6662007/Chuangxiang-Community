"""将人工资料整理为阅读文案；原始正文、版本与维护记录保持不变。"""
import json
import re

from .selectors import public_text


# 仅处理整理时产生的固定模板，不删除赛事规则中的禁止条款或适用条件。
EDITORIAL_LINES = {
    '人工整理摘要，非来源全文。',
    '人工整理的学习导读，非资料原文。',
    '原件按自身届次使用。提取文本未经逐字校对，关键条款的核对范围另注。',
    '附件按原件实际届次使用，未逐页审核的提取文本不作为已核规则。',
    '自动提取用于检索；关键事实单独核对，未逐页审核。',
    '各份学习资料按自己的适用范围使用。',
    '开放状态依据核验日的官方公告，未登录提交或缴费；资料待审核。',
    '只适用于所标届次；当届简讯与往届规则分开使用。',
}
EDITORIAL_LABELS = re.compile(r'^(?:核验程度|审核状态|审核|证据状态|证据情况|核验日期|核验日期与程度)[：:]')
COPY_REPLACEMENTS = {
    '（不代表附件全文已读）': '',
    '；非赛事官方指定教材': '',
    '；不替代最新补充通知': '',
    '资料正文待核对': '资料入口',
    '仅搜索结果，正文待核对': '搜索摘要',
    '；具体对应关系见导读': '',
    '；来源与目录身份差异见导读': '',
    '2026届；高校转载通知中的校内日期不作为同济大学报名日期': '2026届；通知含转载高校的校内安排',
    '；详细章节定位待审核': '',
    '已核整理：': '赛事要点：',
    '结构化字段：': '参与信息：',
    '历史资料，不代表2026报名期限。': '往届资料。',
    '历史届次规则及日期，不代表2026报名期限。': '往届规则与时间。',
    '未核定期限，不代表开放。': '报名时间未收录。',
    '公开页面；工具安装、课程视频与下载条件以提供方页面为准': '公开页面；安装、视频与下载见资源页',
    '公开网页；附件或报名系统另以访问说明为准': '公开网页；附件与报名见对应入口',
    '免费阅读；例题和习题答案范围以教材为准': '免费阅读；例题与答案范围见教材',
    '；现场演唱录制限制以赛事规则为准': '；参赛录制按赛事要求进行',
}

FIELD_LABELS = {
    'level': '赛事范围', 'participation_type': '参赛形式', 'organizer': '主办方',
    'registration_url': '报名入口', 'registration_method': '报名方式',
    'eligibility': '参赛资格', 'tracks': '赛道', 'team_size_min': '最少人数',
    'team_size_max': '最多人数', 'registration_deadline': '报名截止',
    'submission_deadline': '提交截止', 'campus_deadline': '校内截止',
    'registration_deadline_at': '报名截止时刻', 'registration_deadline_timezone': '报名时区',
    'submission_deadline_at': '提交截止时刻', 'submission_deadline_timezone': '提交时区',
    'campus_deadline_at': '校内截止时刻', 'campus_deadline_timezone': '校内时区',
    'deadline_notes': '时间说明', 'campus_arrangements': '校内安排',
}
FIELD_VALUES = {
    'level': {'national': '国家级', 'international': '国际级', 'provincial': '省级', 'campus': '校级', 'unknown': '未注明'},
    'participation_type': {'individual': '个人', 'team': '团队', 'both': '个人或团队', 'unknown': '未注明'},
}


def _readable_mapping(text):
    marker = '字段映射（未知留空）：'
    if marker not in text:
        return text
    before, tail = text.split(marker, 1)
    tail = tail.lstrip()
    try:
        values, end = json.JSONDecoder().raw_decode(tail)
    except (ValueError, TypeError):
        return text
    if not isinstance(values, dict) or not set(values) <= FIELD_LABELS.keys():
        return text
    rows = []
    for key, value in values.items():
        if value is None or value == '':
            continue
        if not isinstance(value, (str, int, float)):
            return text
        value = FIELD_VALUES.get(key, {}).get(str(value), str(value))
        rows.append(f'{FIELD_LABELS[key]}：{value}')
    return before + '\n'.join(rows) + tail[end:]


def reading_text(value, *, gaps=()):
    """精简工作流措辞，保留年份、范围、来源与实质参赛规则。"""
    gap_lines = {public_text(item).strip() for item in gaps if isinstance(item, str)}
    lines = []
    for raw in _readable_mapping(public_text(value)).splitlines():
        line = raw.strip()
        label = re.sub(r'^(?:#{1,6}\s+|[-*]\s+)', '', line).replace('**', '')
        if label in EDITORIAL_LINES or EDITORIAL_LABELS.match(label):
            continue
        if label in ('待补内容：', '仍需补充：', '缺口：') or label in gap_lines:
            continue
        if re.match(r'^附件/[^\s]+\.(?:pdf|docx?|xlsx?|pptx?)$', line, re.I):
            continue
        for before, after in COPY_REPLACEMENTS.items():
            line = line.replace(before, after)
        line = re.sub(r'资料仅适用于([^；\n]+)；日期以来源对应届次为准。', r'适用届次：\1。', line)
        line = re.sub(r'\[src-[a-zA-Z0-9-]+[；;]\s*([^\]]+)\]', r'（\1）', line)
        line = re.sub(r'[，；、]?\s*待审核', '', line)
        if line.strip('。；：:，、 -'):
            lines.append(line)
    return '\n'.join(lines)


def document_summary(body, metadata):
    purpose = reading_text(metadata.get('why_useful'))
    if purpose:
        return purpose[:280]
    lines = [line for line in body.splitlines() if not re.match(
        r'^(?:目录[：:]|目录编号[：:]|目录年份[：:]|资料届次[：:]|采用[：:]|\d{7}\s+|整理正文[：:]|赛事要点[：:])', line)]
    return '\n'.join(lines)[:280]


RESOURCE_LABELS = {
    '类型': 'kind', '难度': 'difficulty', '访问': 'access', '访问条件': 'access',
    '适用': 'audience', '适用对象': 'audience', '适用范围': 'scope',
    '基础要求': 'prerequisites', '语言': 'language',
    '用途': 'purpose', '中文摘要': 'purpose',
    '入门顺序': 'learning_path', '学习方法': 'learning_path',
}


def resource_presentation(value, *, title=''):
    text = reading_text(value)
    facts, paragraphs = {}, []
    for line in text.splitlines():
        if re.match(r'^\d{7}\s+', line) or line == public_text(title):
            continue
        # 第一批资料把类型、难度和访问方式写在同一行。
        parts = re.split(r'[；;](?=(?:难度|访问)[：:])', line) if line.startswith(('类型：', '类型:')) else [line]
        for part in parts:
            match = re.match(r'^([^：:]+)[：:](.*)$', part)
            if match and match[1] in RESOURCE_LABELS:
                key, content = RESOURCE_LABELS[match[1]], match[2].strip()
                if content:
                    facts[key] = content
            elif not re.match(r'^(?:来源链接|来源|发布方|来源定位)[：:]', part):
                if part not in paragraphs:
                    paragraphs.append(part)
    purpose = facts.pop('purpose', '')
    if purpose:
        paragraphs = [line for line in paragraphs if line != purpose]
    summary = purpose or (paragraphs[0] if paragraphs else '')
    content = '\n'.join(([purpose] if purpose else []) + paragraphs)
    return {'summary': summary[:280], 'content': content, 'facts': facts}
