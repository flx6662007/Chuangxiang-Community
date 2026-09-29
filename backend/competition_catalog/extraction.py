"""Deterministic extraction from stored official notices; no network or database writes.

Only source text is evidence. Fetch/publication dates are never edition dates. A
candidate remains reviewable when identity, scope or any deadline is ambiguous.
"""

from datetime import date
from hashlib import sha256
import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit


RULE_VERSION = 'catalog-notice-v1'
_YEAR = r'(?:19|20)\d{2}'
_NUMBER = r'[一二三四五六七八九十两\d]+'
_MAJOR = re.compile(r'^[一二三四五六七八九十]+[、．.]')
_HEADING = re.compile(r'^(?:[一二三四五六七八九十]+[、．.]|[（(][一二三四五六七八九十\d]+[）)]|\d{1,2}(?!\d)(?:\.\d{1,2})*(?:[、．.）)]|\s+))')
_PRIVATE = re.compile(
    r'联系人|联系老师|联系电话|手机(?:号码)?|电话号码|咨询电话|微信号|QQ\s*(?:官)?群|QQ\s*[:：]|'
    r'电子邮箱|官方邮箱|[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|'
    r'(?<!\d)1[3-9]\d{9}(?!\d)|银行账号|开户行|银行账户|收款账号|账\s*号\s*[:：]\s*\d|户\s*名\s*[:：]'
)
_NON_NOTICE = re.compile(
    r'获奖|获奖名单|结果公示|成绩公示|成绩公布|入围名单|晋级名单|晋级通知|颁奖|'
    r'圆满|成功举办|隆重举行|闭幕|落幕|赛事回顾|赛后|喜报|优秀作品展|'
    r'研讨会|论坛|工作会议|学术会议|培训会|志愿者|教师募集|院校联系人|'
    r'专家征集|评委征集|裁判员|优秀指导教师|新闻报道|承办单位征集|分赛区征集|参赛分享|参赛者登录'
)
_INTENT = re.compile(r'关于举办|关于开展|关于组织|报名|参赛|征集|征稿|启动|竞赛通知|大赛通知|比赛通知|竞赛章程|竞赛规则|比赛规则|参赛指南|邀请函')
_REG = re.compile(r'报名|注册参赛|车队注册|注册截止')
_SUBMIT = re.compile(r'作品(?:提交|征集|征稿|报送)|提交.{0,6}(?:作品|参赛文件|方案|成果)|交稿|投稿|征稿|材料提交|提交材料|作品上传|方案提交|成果提交')
_DATE = re.compile(r'(?:(?P<year>20\d{2})\s*[年./-]\s*)?(?P<month>\d{1,2})\s*[月./-]\s*(?P<day>\d{1,2})\s*日?')


def _normal(value):
    value = unicodedata.normalize('NFKC', str(value or '')).lower()
    value = re.sub(r'第[一二三四五六七八九十百\d]+届', '', value)
    value = re.sub(r'(?:19|20)\d{2}(?:年|年度|赛季|版)?', '', value)
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', value)


def _headline(raw):
    title = str(raw or '').strip()
    title = re.split(r'\s+[|｜_\-]\s+|(?<=通知)[-_]|(?<=公告)[-_]|_', title, maxsplit=1)[0]
    # These wrappers carry no event identity. Keep actual track names intact.
    title = re.sub(r'^.{0,12}[丨|｜](?=关于|20\d{2}|第)', '', title)
    title = re.sub(r'^(?:竞赛通知|大赛通知|赛事通知)[丨|｜:：]\s*', '', title)
    title = re.sub(r'^(?:.{0,15}?关于(?:举办|开展|组织)|转发[:：]?|【通知】|通知[:：])\s*', '', title)
    title = re.sub(r'(?:将于|定于)\d{1,2}月.*$', '', title)
    title = re.sub(r'【更新版】|[（(]更新版[）)]', '', title)
    title = re.sub(r'(?<=赛)通知(?=[–—-])', '', title)
    title = re.sub(r'(?<=赛)通知$', '', title)
    title = re.sub(r'(?:的通知|报名通知|启动公告|参赛说明|报名须知|参赛通知|报名公告|征稿通知|赛事通知|报名启动|开始报名|启动通知|参赛指南|参赛细则|竞赛方案|预报名)$', '', title)
    return title.strip(' ：:—-，,')[:200]


def _belongs(row, headline):
    target = _normal(headline)
    names = [row.get('entry_name', ''), *(row.get('aliases') or [])]
    for name in names:
        if not isinstance(name, str):
            continue
        # Parentheses may contain an official abbreviation, not an additional
        # mandatory part of the Chinese event's name.
        main = re.split(r'[（(]', name, maxsplit=1)[0]
        for variant in (name, main):
            norm = _normal(variant)
            if len(norm) >= 6 and norm in target:
                return True
            if re.fullmatch(r'[A-Za-z][A-Za-z0-9 -]{1,20}', variant or ''):
                if re.search(r'(?<![A-Za-z0-9])' + re.escape(variant) + r'(?![A-Za-z0-9])', headline, re.I):
                    return True
            # Optional audience/scope prefixes vary in official headings. The
            # distinctive contest name still has to match, never just a topic.
            core = re.sub(r'^(?:全国|中国|国际)?(?:高校|大学生|学生)', '', norm)
            core = re.sub(r'^uia', '', core)
            if len(core) >= 8 and core in target:
                return True
        # The named sponsor may sit between the quoted brand and official name.
        if '挑战杯' in name:
            tail = _normal(name.split('挑战杯', 1)[1])
            if tail and '挑战杯' in target and tail in target:
                return True
    return False


def _heading_depth(line):
    if _MAJOR.match(line):
        return 1
    match = re.match(r'^(\d{1,2}(?!\d)(?:\.\d{1,2})*)(?:[、．.)）]|\s+)', line)
    if match:
        return 2 + match.group(1).count('.')
    if re.match(r'^[（(][一二三四五六七八九十\d]+[）)]', line):
        return 3
    return 0


def _article(row):
    lines = [line.strip() for line in str(row.get('body') or '').splitlines() if line.strip()]
    attached = '以下为附件正文：' in lines
    if attached:
        lines = lines[lines.index('以下为附件正文：') + 1:]
    if attached or urlsplit(str(row.get('url') or '')).path.lower().endswith('.pdf'):
        # PDF line wrapping is not a paragraph boundary. Join only continuing
        # lines, and never cross a page marker or numbered section. Evidence
        # remains the same source sequence after whitespace normalization.
        joined, can_join = [], False
        for line in lines:
            if re.fullmatch(r'[—–-]?\s*\d{1,3}\s*[—–-]?', line):
                can_join = False
                continue
            if can_join and joined and len(joined[-1]) > 25 and len(joined[-1]) < 2000 and not re.search(r'[。；;：:！？!?]$', joined[-1]) and not _HEADING.match(line):
                joined[-1] += line
            else:
                joined.append(line)
            can_join = True
        lines = joined
    raw_title = re.split(r'\s+[|｜_\-]\s+', str(row.get('title') or ''), maxsplit=1)[0].strip()
    for index, line in enumerate(lines[:100]):
        if raw_title and line == raw_title:
            lines = lines[index + 1:]
            break
    for index, line in enumerate(lines):
        if re.match(r'^(?:热门动态|相关阅读|相关文章|推荐阅读|上一篇|下一篇|友情链接|网站地图|版权所有|Copyright|版权声明|CCF聚焦)(?:\s|[:：]|$)', line, re.I):
            lines = lines[:index]
            break
    # Private contact/payment sections do not enter public excerpts. Restore
    # later independent numbered sections, e.g. 十一、其他事项 after contacts.
    public = []
    private_section, private_depth = False, 0
    for line in lines:
        current_depth = _heading_depth(line)
        if current_depth and private_section and current_depth <= private_depth:
            private_section = False
        if len(line) < 40 and re.search(r'联系方式|联系信息|联系人|缴费方式|付款方式|汇款方式', line):
            private_section = True
            private_depth = current_depth or 1
        if private_section:
            continue
        unsafe_link = any(not _safe_url(m.group().rstrip('，。；;、')) for m in re.finditer(r'https?://[^\s，。；;<>"）)]+', line))
        if unsafe_link:
            continue
        if _PRIVATE.search(line):
            # Preserve an independently stated deadline even if another clause
            # on the same line contains an email address. Otherwise a conflict
            # could disappear solely because contact details were removed.
            public.extend(part.strip() for part in re.split(r'[，,；;。]', line) if part.strip() and not _PRIVATE.search(part))
        else:
            public.append(line)
    return public


def _section(lines, labels, limit=5000):
    for index, line in enumerate(lines):
        clean = _HEADING.sub('', line).strip(' ：:')
        if not any(clean == label or re.match(re.escape(label) + r'\s*[:：]', clean) for label in labels):
            continue
        level = _heading_depth(line)
        selected = [line]
        for following in lines[index + 1:]:
            following_level = _heading_depth(following)
            if (level and following_level and following_level <= level) or (not level and (re.fullmatch(r'\d{1,2}', following) or _MAJOR.match(following))):
                break
            selected.append(following)
            if len('\n'.join(selected)) >= limit:
                break
        return '\n'.join(selected)[:limit]
    return ''


def _organizer(lines):
    for index, line in enumerate(lines):
        clean = _HEADING.sub('', line).strip()
        if re.match(r'^主办(?:单位|方|机构)?\s*[:：]', clean):
            value = re.split(r'[:：]', clean, maxsplit=1)[1].strip()
            if value:
                return value[:500], line
        if clean.strip(' ：:') in ('主办单位', '主办方', '主办机构'):
            values = []
            for following in lines[index + 1:index + 8]:
                if _HEADING.match(following) or re.search(r'承办|协办|支持单位|指导单位|组织机构', following):
                    break
                values.append(following)
            if values:
                return '\n'.join(values)[:500], '\n'.join([line, *values])
        match = re.search(r'由([^，。；：]{3,400}?)(?:发起并|联合|共同)?主办', line)
        if match:
            return match.group(1), line
        match = re.search(r'(?:^|，)([^，。；：]{3,120}?)(?:决定|将|拟)(?:继续)?举办(?:第.{1,8}届)?', line)
        if match and re.search(r'学会|协会|大学|委员会|教育部|人民政府', match.group(1)):
            return match.group(1), line
    return '', ''


def _number(value):
    if value.isdigit():
        return int(value)
    numbers = {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
    if value in numbers:
        return numbers[value]
    if '十' in value:
        left, right = value.split('十', 1)
        return numbers.get(left, 1) * 10 + numbers.get(right, 0)
    return None


def _participation(lines):
    selected = [line for line in lines if re.search(r'团队|队员|参赛队|小组|团体赛|个人参赛|单人参赛|个人赛|组队|个人或', line)]
    evidence, lows, highs = [], set(), set()
    individual, team = False, False
    for line in selected:
        if re.search(r'个人赛|个人参赛|单人参赛|个人(?:或|和|与)团队|个人(?:或|和|与)组队', line):
            individual = True
            evidence.append(line)
        if re.search(r'团体赛|团队(?:报名)?参赛|(?:采取|采用).{0,8}团队(?:报名|形式|方式)|(?:为|采用|采取)团队赛|个人(?:或|和|与)团队|允许组队|组队参赛|以小组形式报名', line):
            team = True
            evidence.append(line)
        # Never let a teacher quota become the student-team quota. Split at
        # punctuation, then demand a team/member/student subject in that clause.
        for clause in re.split(r'[，,。；;]', line):
            if re.search(r'教师|导师|教练|作者|作品', clause) or not re.search(r'参赛团队|每支团队|每个团队|每队|每支队伍|学生人数|参赛队员|团队成员|正式队员|小组人数', clause):
                continue
            range_match = re.search(r'(' + _NUMBER + r')\s*(?:至|到|[-—~～])\s*(' + _NUMBER + r')\s*[人名]', clause)
            maximum = re.search(r'(?:不超过|最多|至多|上限(?:为)?|不得超过|不多于)\s*(' + _NUMBER + r')\s*[人名]', clause)
            exact = re.search(r'(?:每队|每支队伍|每个(?:参赛)?团队)(?:由|为|有)?\s*(' + _NUMBER + r')\s*[人名](?:组成)?\s*$', clause)
            if range_match:
                lows.add(_number(range_match.group(1)))
                highs.add(_number(range_match.group(2)))
            elif maximum:
                highs.add(_number(maximum.group(1)))
            elif exact:
                lows.add(_number(exact.group(1)))
                highs.add(_number(exact.group(1)))
            if range_match or maximum or exact:
                team = True
                evidence.append(line)
    errors = []
    if len(lows) > 1 or len(highs) > 1:
        errors.append('不同参赛组别或条款的人数限制不一致，需人工区分。')
    low = next(iter(lows), None) if len(lows) <= 1 else None
    high = next(iter(highs), None) if len(highs) <= 1 else None
    kind = 'both' if individual and team else 'team' if team else 'individual' if individual else 'unknown'
    return kind, low, high, '\n'.join(dict.fromkeys(evidence)), errors


def _dates_in(text, year):
    dates, invalid = [], False
    current_year = year
    for match in _DATE.finditer(text):
        if match.group('year'):
            current_year = int(match.group('year'))
        if not current_year:
            continue
        try:
            dates.append((date(current_year, int(match.group('month')), int(match.group('day'))), match.start(), match.end()))
        except ValueError:
            invalid = True
    return dates, invalid


def _deadlines(lines, year):
    values = {'registration_deadline': [], 'submission_deadline': []}
    evidence = {}
    notes, errors = [], []
    context, context_line, context_age = [], '', 0
    for line in (part.strip() for original in lines for part in re.split(r'[，,；;。]', original) if part.strip()):
        context_age += 1
        if context_age > 2 or re.fullmatch(r'\d{1,2}', line):
            context, context_line = [], ''
        if _HEADING.match(line) or (len(line) < 40 and re.search(r'报名时间|投稿时间|提交时间|作品提交|征稿时间', line)):
            context = []
            heading_text = _HEADING.sub('', line).strip()
            if len(line) <= 60 and _REG.search(line) and (re.match(r'^(?:大赛|参赛)?报名', heading_text) or re.search(r'时间|截止', heading_text)):
                context.append('registration_deadline')
            if len(line) <= 60 and _SUBMIT.search(line):
                context.append('submission_deadline')
            context_line = line
            context_age = 0
        fields = []
        if _REG.search(line):
            fields.append('registration_deadline')
        if _SUBMIT.search(line):
            fields.append('submission_deadline')
        # A bare date/range beneath a relevant heading inherits that heading.
        if not fields and context and (re.match(r'^(?:赛程时间|时间|日期)[:：]', line) or re.match(r'^(?:20\d{2}\s*年|\d{1,2}月)', line)):
            fields = context
        if not fields:
            continue
        if re.search(r'模拟|缴费|抢车号|培训|打印|答辩|比赛日期|开始报名|起开始|开启报名|开放报名', line) and '截止' not in line and '截至' not in line:
            continue
        dates, invalid = _dates_in(line, year)
        if invalid:
            errors.append('截止日期中存在无效日历日期。')
        if not dates:
            continue
        snippet = '\n'.join(dict.fromkeys([context_line, line])) if context_line and set(fields) == set(context) else line
        # A start date alone is not a deadline.
        end_word = re.search(r'截止(?:时间|日期)?\s*[:：为至到]?|截至|最迟', line)
        is_range = len(dates) >= 2 and bool(re.search(r'[-—–~～至到]', line[dates[0][2]:dates[-1][1]]))
        if re.search(r'延期|延长|调整|推迟|提前|变更', line) and len({item[0] for item in dates}) > 1:
            errors.append('截止日期有延期或调整的多个日期，需人工确认生效日期。')
            notes.append(snippet)
            continue
        if end_word:
            after = [item for item in dates if item[1] >= end_word.end()]
            if len(after) == 1:
                chosen = after[0][0]
            elif len(after) > 1:
                errors.append('同一截止条款含多个日期，需区分阶段或适用对象。')
                notes.append(snippet)
                continue
            elif re.search(r'(?:前|止|截止)', line[dates[-1][2]:]):
                chosen = dates[-1][0]
            else:
                continue
        elif is_range:
            chosen = dates[-1][0]
        elif re.search(r'(?:至|到)\s*(?:20\d{2}\s*年)?\d{1,2}月', line) or re.search(r'(?:报名|征稿|投稿).{0,12}时间.{0,8}即日起', line):
            chosen = dates[-1][0]
        elif re.search(r'\d{1,2}日\s*(?:前|止)', line):
            chosen = dates[-1][0]
        elif len(dates) == 1 and re.search(r'报名.{0,12}[（(]20\d{2}\s*年\d{1,2}月\s*[-—至]', line):
            chosen = dates[0][0]
        else:
            continue
        notes.append(snippet)
        for field in fields:
            values[field].append(chosen)
            evidence.setdefault(field, []).append(snippet)
    result = {}
    for field, dates in values.items():
        unique = set(dates)
        result[field] = next(iter(unique)).isoformat() if len(unique) == 1 else None
        if len(unique) > 1:
            errors.append(('报名' if field.startswith('registration') else '作品提交') + '存在不同阶段或对象的多个截止日，不能合并为一个日期。')
        if field in evidence:
            evidence[field] = '\n'.join(dict.fromkeys(evidence[field]))
    return result, evidence, '\n'.join(dict.fromkeys(notes))[:5000], errors


def _safe_url(value):
    try:
        parts = urlsplit(value)
        if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username or parts.password:
            return False
        host = parts.hostname.lower().rstrip('.')
        if host in ('localhost', 'example.com', 'example.org', 'example.net') or host.endswith(('.localhost', '.local', '.example.com', '.example.org', '.example.net')):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return '.' in host
    except ValueError:
        return False


def _category(title):
    for regex, code, name in (
        (r'数学|统计|建模', 'mathematics', '数学与建模'),
        (r'计算机|程序设计|软件|网络|信息安全|CCSP|CSP|人工智能|数字媒体', 'computer-science', '计算机与人工智能'),
        (r'建筑|土木|规划|测绘|BIM', 'construction', '建筑与土木'),
        (r'电子|机械|工程|机器人|方程式|汽车|智能制造', 'engineering', '工程与技术'),
        (r'设计|艺术|音乐|美术|广告|摄影', 'design-arts', '设计与艺术'),
        (r'英语|外语|日语|翻译|写作|文学', 'language-humanities', '语言与人文'),
        (r'创业|创新|挑战杯|互联网', 'innovation', '创新创业'),
    ):
        if re.search(regex, title, re.I):
            return code, name
    return 'general', '综合赛事'


def extract_notice(row: dict, *, today: date) -> dict:
    """Return source-grounded public fields plus review metadata, never publish.

    Required input keys: entry_code, entry_name, aliases, title, body. Other
    monitor fields are accepted but never treated as evidence of a current year.
    Evidence maps to raw title/body excerpts, including for normalized values.
    """
    raw_title = str(row.get('title') or '').strip()
    associated = re.match(r'^关联通知：([^\n]+)\n关联通知地址：https?://[^\n]+\n以下为附件正文：', str(row.get('body') or ''))
    identity_title = associated.group(1).strip() if associated else raw_title
    title = _headline(identity_title)
    candidate = {
        'code': '', 'title': title, 'edition': '', 'summary': '', 'description': '',
        'organizer': '', 'tracks': '', 'eligibility': '', 'participation_type': 'unknown',
        'team_size_min': None, 'team_size_max': None, 'registration_method': '',
        'registration_url': '', 'registration_deadline': None, 'submission_deadline': None,
        'deadline_notes': '', 'level': 'unknown',
    }
    candidate['category_code'], candidate['category_name'] = _category(title)
    result = {'candidate': candidate, 'evidence': {'title': identity_title}, 'missing_fields': [],
              'errors': [], 'disposition': 'review', 'rule_version': RULE_VERSION}
    evidence, errors = result['evidence'], result['errors']
    attachment_parent_years = set()
    if associated:
        actual_body = str(row.get('body') or '')[associated.end():].lstrip()
        actual_lines = [line.strip() for line in actual_body.splitlines() if line.strip()][:15]
        title_parts = []
        for index, line in enumerate(actual_lines):
            if (not _HEADING.match(line) and len(line) < 250
                    and not re.match(r'^(?:比赛|竞赛)(?:时间|地点|安排|要求|通知)', line)
                    and re.search(r'竞赛|大赛|擂台赛|挑战赛|比赛', line)):
                if len(_normal(line)) < 12 and index and not re.fullmatch(r'附件\s*\d+|\d+', actual_lines[index - 1]):
                    title_parts.append(actual_lines[index - 1])
                title_parts.append(line)
                for following in actual_lines[index + 1:index + 4]:
                    if len(following) < 80 and re.search(r'赛区|区域赛|专项赛|第.{1,6}轮|^比赛通知$|^章程$|^规则$', following):
                        title_parts.append(following)
                    else:
                        break
                break
        possible_title = ''.join(title_parts)
        # A parent page may link another independent competition's regulations.
        # Parent provenance proves where an attachment came from, not its scope.
        if possible_title and not _belongs(row, possible_title):
            result['disposition'] = 'irrelevant'
            errors.append('附件自身标题指向另一赛事，不能用父通知的目录归属替代。')
            return result
        if not possible_title or not _belongs(row, possible_title):
            errors.append('附件正文开头未能独立确认对应赛事，父通知仅作为来源关联。')
            return result
        attachment_parent_years = set(re.findall(_YEAR, identity_title))
        attachment_years = set(re.findall(_YEAR, possible_title))
        if attachment_parent_years and attachment_years and attachment_parent_years != attachment_years:
            errors.append('附件赛事年度与关联通知不一致，需复核适用届次。')
            return result
        identity_title = possible_title
        title = _headline(identity_title)
        candidate['title'] = title
        candidate['category_code'], candidate['category_name'] = _category(title)
        evidence['title'] = '\n'.join(title_parts)
    if not _belongs(row, title):
        errors.append('通知标题不能明确归属于该目录赛事；正文提到其他赛事不足以建立归属。')
        result['disposition'] = 'irrelevant'
        return result
    if _NON_NOTICE.search(identity_title):
        errors.append('这是获奖、活动报道或其他非参赛征集通知。')
        result['disposition'] = 'irrelevant'
        return result
    lines = _article(row)
    if not _INTENT.search(identity_title) and not associated:
        # A named article may use an event title alone, but a homepage or list
        # of links must not borrow registration facts from unrelated notices.
        if row.get('page_kind') == 'index' or not any(re.search(r'现.{0,15}(?:举办|开启|报名|征集)|现将.{0,15}(?:通知|安排)', line) for line in lines[:8]):
            errors.append('页面缺少明确的本赛事参赛通知语境，可能为首页或列表。')
            result['disposition'] = 'irrelevant'
            return result
    years = set(re.findall(_YEAR, title))
    if len(years) == 1:
        year = int(next(iter(years)))
        evidence['edition'] = identity_title
    else:
        year = None
        # Only the leading announcement sentence may establish a missing year.
        for line in lines[:8]:
            found = set(re.findall(_YEAR, line))
            if len(found) == 1 and _belongs(row, line) and re.search(r'举办|举行|开启|启动|赛季', line) and not re.search(r'发布时间|发表于|纳入|已于', line):
                year = int(next(iter(found)))
                evidence['edition'] = line
                break
        if year is None:
            # An explicitly named edition can span into the following year's
            # final. Its own stated initial round identifies the starting year,
            # unlike a publication date or the year of an unrelated award list.
            for line in lines:
                match = re.search(r'本届(?:竞赛|大赛)(?:初赛|报名|选拔赛)(?:定于|将于|于)\s*(20\d{2})\s*年', line)
                if match and re.search(r'第[一二三四五六七八九十百\d]+届', title):
                    year = int(match.group(1))
                    evidence['edition'] = line
                    break
        if year is None and associated and len(attachment_parent_years) == 1:
            year = int(next(iter(attachment_parent_years)))
            evidence['edition'] = associated.group(1)
    if year:
        candidate['edition'] = str(year)
        stable = _normal(title)
        candidate['code'] = f"catalog-{row.get('entry_code', '')}-{year}-{sha256(stable.encode()).hexdigest()[:10]}"
    else:
        errors.append('原文未能明确当前通知对应的赛事年度；不得使用采集日期或新闻发布日期代替。')

    for field, labels in (
        ('eligibility', ('参赛对象', '竞赛对象', '参赛资格', '参赛要求', '参赛范围', '参赛人员', '参赛条件', '报名方式及要求', '预报名要求')),
        ('tracks', ('参赛选题', '大赛赛项', '竞赛赛项', '竞赛内容', '大赛内容', '竞赛题目说明', '赛道设置', '竞赛组别', '竞赛分类及内容')),
        ('registration_method', ('报名流程', '报名方式', '参赛报名', '报名程序', '报名办法', '参赛方式', '报名方式及要求')),
    ):
        value = _section(lines, labels)
        if value and (len(value.splitlines()) > 1 or re.search(r'[:：].+', value)):
            candidate[field] = value
            evidence[field] = value
    organizer, source = _organizer(lines)
    candidate['organizer'] = organizer
    if organizer:
        evidence['organizer'] = source

    kind, low, high, source, participation_errors = _participation(lines)
    candidate.update(participation_type=kind, team_size_min=low, team_size_max=high)
    if source:
        for field in ('participation_type', 'team_size_min', 'team_size_max'):
            if candidate[field] not in (None, 'unknown'):
                evidence[field] = source
    errors.extend(participation_errors)
    deadlines, date_evidence, notes, date_errors = _deadlines(lines, year)
    candidate.update(deadlines)
    evidence.update(date_evidence)
    candidate['deadline_notes'] = notes
    if notes:
        evidence['deadline_notes'] = notes
    errors.extend(date_errors)
    if not candidate['registration_method']:
        methods = [line for line in lines if re.search(r'(?:通过|登录|登陆|进入).{0,120}(?:官网|网站|平台|系统|服务网|竞赛网|https?://).{0,100}(?:报名|注册)|报名.{0,40}(?:官网|网站|平台|系统)', line) and not re.search(r'获奖|公示|不得|禁止', line)]
        if methods:
            candidate['registration_method'] = '\n'.join(methods)[:5000]
            evidence['registration_method'] = candidate['registration_method']
    # Do not infer an exact time or time zone; retain original wording in notes.
    if candidate['registration_method']:
        for match in re.finditer(r'https?://[^\s，。；;<>"）)]+', candidate['registration_method']):
            url = match.group().rstrip('，。；;、')
            if _safe_url(url):
                candidate['registration_url'] = url
                evidence['registration_url'] = match.group()
                break
    if re.search(r'区域赛|选拔赛|赛区|校级|校内', title):
        # A global event brand does not make a regional selection international.
        pass
    elif re.search(r'国际|世界', title):
        candidate['level'] = 'international'
        evidence['level'] = raw_title
    elif re.search(r'全国|中国大学生', title):
        candidate['level'] = 'national'
        evidence['level'] = raw_title

    intro = _section(lines, ('大赛简介', '竞赛简介', '赛事简介'), limit=500)
    if not intro:
        intro = next((line for line in lines[:12] if len(line) > 40 and _belongs(row, line) and not re.search(r'版权|发布时间|发表于', line)), '')[:500]
    candidate['summary'] = intro or raw_title[:500]
    evidence['summary'] = candidate['summary']
    excerpts = [candidate['summary']]
    for field in ('organizer', 'tracks', 'eligibility', 'registration_method', 'deadline_notes'):
        if candidate[field]:
            excerpts.append(candidate[field])
    candidate['description'] = '\n'.join(dict.fromkeys(excerpts))[:20000]
    evidence['description'] = candidate['description']
    result['missing_fields'] = [field for field in ('edition', 'organizer', 'tracks', 'eligibility', 'registration_method', 'registration_url', 'registration_deadline', 'submission_deadline', 'team_size_min', 'team_size_max') if candidate[field] in ('', None)]
    if kind == 'unknown':
        result['missing_fields'].append('participation_type')
    if not candidate['organizer']:
        errors.append('缺少可核验的主办单位。')
    if not candidate['eligibility']:
        errors.append('缺少可核验的参赛对象或资格。')
    actual_deadlines = [date.fromisoformat(value) for value in deadlines.values() if value]
    if not actual_deadlines:
        errors.append('缺少明确的报名或作品提交截止日，暂不能判定为当前可参加赛事。')
    if not errors:
        # Registration decides availability when present; a later submission
        # deadline never reopens already-closed registration.
        effective = candidate['registration_deadline'] or candidate['submission_deadline']
        result['disposition'] = 'historical' if year < today.year or date.fromisoformat(effective) < today else 'ready'
    result['errors'] = list(dict.fromkeys(errors))
    return result
