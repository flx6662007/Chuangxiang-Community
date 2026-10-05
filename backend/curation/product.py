"""Pure transformations for the student competition library.

The source packages remain research records.  Only explicitly supported facts
cross into the product view; no database publication takes place here.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from urllib.parse import urlsplit


PROCESS = re.compile(
    r'本轮|本次|本包|入库|草稿|待审核|待核|未核|尚未|尚缺|未找到|未确认|未公开确认|'
    r'字段映射|结构化字段|核验程度|证据状态|证据情况|人工整理|来源全文|'
    r'不代表|不替代|不能据此|不能把|不得作为|不作为|只作|仅作|'
    r'身份线索|详细章节定位|检索命中|资料入口（标题|访问失败|网页直读|读取超时|'
    r'正文读取|缺口|自动提取|未逐|后续补|待补|待人工|未解包|已读页面|未取得|'
    r'后台|数据库|JSON|JSONL|metadata|schema_version', re.I)
EDITORIAL = re.compile(
    r'不擅自|另查|只能证明|已读|已核对|已确认|归档依据|对应关系|口径|本记录|'
    r'(?:应按|需按|须按|须逐项).*核对|须核对|需读(?:EV|CV|AV)|报名前须阅读|'
    r'应合并核对|原PDF|网页元数据|未成功取得|待主办|已取得最终版|'
    r'以主办方.*核对|不能用于同济|不推定|以组委会后续公告为准|'
    r'之后赛程有调整|提交前应核对|列(?:对象|组队)|目录.*旧称|'
    r'通知含.*约定|其他成员资格.*核对|不得简化|不能简化|还需详细条款|现为历史期限|研究生构成另有|'
    r'来源.*范围|原文.*差异|初始通知.*差异|通知提供.*附件.*核对|全文可读|通知正文可读|适合作为早期方案背景|'
    r'不能用旧评分|不能用一个统一报名状态|信息以本届官网为准|以主办方\d*通知为准|'
    r'目录城市设计.*以.*为准|各报告报名截止以组委会通知为准|'
    r'现阶段可核验|加载失败|不能据标题推断|该日期是历史截止|'
    r'以组委会当年样题为准|详细命题仍以官方专题为准|详细赛道技术规范仍以附件参赛指南为准|'
    r'以具体赛题的平台限制为准|后页以原件为准|各报告和报名截止时间以组委会通知为准|'
    r'跨赛区参赛限制以通知为准|不把|不将|不得将|不能将|不能换成|不能套|不能混|不能通用|'
    r'不能直接|不直接适用于|不适用于同济|不套用到同济|不录为同济|不能作为中国|'
    r'不是报名|不是15名|不是现在|不是完整|不是本届|不是本赛事|不是赛事|不是组委会|'
    r'不等于(?:可|满足|课程|团队)|不以一般学生资格替代|不当作确定|'
    r'原文未给|未给精确|未全部|未展开|未完整展开|未进一步|未补齐|未宣称|未附|'
    r'保留差异|差异仍保留|保留原文|保留原标签|采用届次改为|原档案误标|两阶段跨年须保留|'
    r'细则仍另核|条件另核|权限另核|版本需另核|要求需另核|当届科目另核|'
    r'本机|本地留存|不留存|不宣称|不搬运|未代为授权|存在性由|非赛事指定|'
    r'非.{0,15}指定(?:教材|题库|工具)|并非所有赛道|不视为公共资源|'
    r'不是.*(?:题库|题集|评分|规程)|非.*(?:真题|评分|完整赛制|个体诊疗)|'
    r'需进入平台确认|预告不等于|需重新核对|已打开|已阅读|下载条件|现场版本|'
    r'官网URL缺失|装载方式未解释|保留歧义|上传数量歧义|具体报名末日需|'
    r'准确报名末日需|结构化报名|页面中其他赛事|拟定时间需留意|不是学生自行|'
    r'按此版本理解规则|赛程文字差异|原文.*误标|校内安排不能|不写成|不猜|不能假定|'
    r'同济(?:属|为).{0,8}赛区|不接受将外校.*同济|原创与版权条款较具体|应在提交前逐项阅读')
AFFILIATION = re.compile(r'同济(?:大学)?(?:校内|校选|报名|推荐|名额|截止|规则|本科生学科竞赛目录)|'
                         r'(?:来自|就读于|我们|团队所属).*同济|我校|本校|校内认定|责任学院|目录等级')
FIELD_LABELS = {
    'organizer': '主办单位', 'eligibility': '参赛对象', 'tracks': '赛道',
    'participation_type': '参赛形式', 'team_size_min': '队伍最少人数',
    'team_size_max': '队伍最多人数', 'registration_method': '报名方式',
    'registration_url': '报名入口', 'registration_start': '报名开始',
    'registration_deadline': '报名截止', 'submission_deadline': '作品提交截止',
}
HARD_FIELDS = {'eligibility', 'education', 'grades', 'majors', 'participation_type',
               'team_size_min', 'team_size_max', 'registration_start',
               'registration_deadline', 'submission_deadline', 'registration_url'}
DISPLAY_VALUES = {'individual': '个人参赛', 'team': '团队参赛', 'both': '个人或团队参赛'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def clean_text(value):
    """Remove editorial clauses, preserving real prohibitions in contest rules."""
    if not isinstance(value, str):
        return ''
    text = re.sub(r'[ \t]+', ' ', value).strip()
    text = re.sub(r'本次(比赛|竞赛|大赛|参赛)', r'\1', text)
    text = re.sub(r'官方第(\d+)届赛题目录列出', r'第\1届设置', text)
    text = re.sub(r'A4\.2\.1[^。]*核对[^。]*。', '', text)
    text = re.sub(r'，选题时需核对[^。]*', '', text)
    text = re.sub(r'，\d{4}初、决赛安排可由[^。]*核对', '', text)
    text = text.replace('承办高校后续报道确认', '').replace('报道的举办日期', '举办日期')
    text = text.replace('生成式AI并非无条件允许：如用于写作，', '使用生成式AI写作时，')
    text = text.replace('需核对虚假内容及抄袭。', '检查生成内容的事实准确性与原创性。')
    text = text.replace('其他类别以各分项邮箱为准', '其他类别使用对应类别的投稿邮箱')
    text = re.sub(r'不要与20\d{2}[^。]*。|这是历史规则[^。]*。|仅用于理解往届[^。]*。', '', text)
    text = re.sub(r'具体个人/团体时段需主办方安排[^。]*。', '', text)
    text = re.sub(r'官网报名栏写9月21日截止[^。]*。|赛程段写报名截至8月31日[^。]*。|报名页期限为9月21日[^。]*。', '', text)
    text = text.replace('历史截止', '截止') if '该日期是历史截止' not in text else text
    paragraphs = []
    for line in text.splitlines():
        # Such sentences describe another campus's quota or timetable. Keeping
        # the first half after deleting the warning would change applicability.
        if re.search(r'(?:不适用于|不能作为|不得作为).*同济|同济.*(?:校内|推荐|报名|名额|截止)', line):
            continue
        parts = re.split(r'(?<=[。！？；;])', line)
        kept = []
        for part in parts:
            part = re.sub(r'[，,](?:本次|本轮|尚未|未逐|不能把|不代表|不替代|当前依据).*$', '', part)
            part = re.sub(r'[，,][^，,。；;]*(?:不代表|不替代|待核|未取得|应合并核对|以组委会通知为准|按通知执行)[^。；;]*', '', part)
            # Drop editorial side clauses while retaining the concrete rule.
            clauses = re.split(r'[，,]', part)
            part = '，'.join(clause for clause in clauses if not EDITORIAL.search(clause)
                            and not re.search(r'须另核|可按对应作品类型核对', clause))
            if PROCESS.search(part) or AFFILIATION.search(part):
                continue
            part = re.sub(r'^[•·\-]\s*', '', part).strip(' ；;')
            if part:
                kept.append(part)
        if kept:
            paragraphs.append('；'.join(kept).replace('。；', '。'))
    return '\n'.join(paragraphs).strip(' ；;')


def edition_label(value):
    value = re.sub(r'[（(][^）)]*(?:待核|回溯|待确认|备赛资料|历史资料|线索)[^）)]*[）)]', '', value).strip()
    if re.search(r'已核|核实|核对|本次|保留|已发布|通知|记录|目录|资料|不表示|当前|官方|官网|已公布|已找到|应分别', value):
        years = list(dict.fromkeys(re.findall(r'(?:19|20)\d{2}', value)))
        ordinal = re.search(r'第[一二三四五六七八九十百零\d]+届', value)
        period = ('—'.join(years[:2]) + ('赛季' if len(years) > 1 else '年')) if years else ''
        return '·'.join(part for part in (period, ordinal[0] if ordinal else '') if part)
    return value


def product_title(title, edition, record_id=''):
    """Remove a catalog year that conflicts with the actual edition identity."""
    edition_year = re.search(r'(?:19|20)\d{2}', edition)
    if not edition_year:
        # Stable legacy IDs encode the source edition year even when the
        # public label is an ordinal only, such as "第十四届".
        identity_year = re.fullmatch(r'curated-c\d+-((?:19|20)\d{2})-\d+', record_id)
        actual_year = identity_year[1] if identity_year else None
    else:
        actual_year = edition_year[0]
    title_years = re.findall(r'(?:19|20)\d{2}', title)
    if actual_year and any(year != actual_year for year in title_years):
        return re.sub(r'[（(](?:19|20)\d{2}[）)]|(?:19|20)\d{2}年?', '', title).strip()
    return title


def public_fact(text):
    # Campus-specific selection details are not general entry requirements.
    if re.search(r'该校(?:名额|推荐|截止)|外校(?:选拔|推荐|遴选)|(?:同济|我校|本校).*(?:选拔|校赛)', text or ''):
        return ''
    if re.search(r'数字不一致|又写12900', text or ''):
        return ''
    if re.search(r'通知提供.*附件.*核对', text or ''):
        return ''
    return clean_text(text)


def fact_heading(text, locator=''):
    for pattern, heading in [
        (r'参赛对象|参赛资格|参赛条件|在校本科|在籍本科|在读本科|大学生组|全日制.*(?:本科|学生)|德语专业.*学生|^面向.*(?:学生|本科|研究生)|^在校学生', '参赛对象'),
        (r'组队|每队|每个团队|队伍人数|每校每个类别|口辩选手|校方指定指导', '组队要求'),
        (r'截止|赛程|赛期|\d+月\d+|开赛|举行', '赛程安排'),
        (r'报名|注册|推荐', '报名方式'),
        (r'作品|视频|格式|论文|机试|提交|总分|评分|平台|报告|笔试|命题|指定成图软件', '作品要求'),
    ]:
        if re.search(pattern, text):
            return heading
    return '赛事介绍'


def campus_selection_source(source):
    """A local selection notice cannot establish national eligibility/dates."""
    return bool(re.search(r'校内|校赛|院内|选拔|遴选|校级|我校|本校', source.get('title', '')))


def render_edition(entry, edition):
    lines = [clean_text(entry.get('current_name') or entry['name']), edition_label(edition['label'])]
    for fact in edition.get('facts', []):
        text = public_fact(fact.get('text', ''))
        if text and fact.get('source_id'):
            lines.append(text)
    return '\n\n'.join(dict.fromkeys(lines))


def render_overview(entry):
    record, _ = build_overview_record(entry, entry.get('checked_on', ''))
    if record:
        return record_text(record)
    return clean_text(entry['name'])


def render_resource(resource):
    resource = prepare_resource(resource)
    parts = [resource.get('title', '')]
    seen = set()
    for key, label in [('summary', ''), ('audience', '适用对象'),
                       ('prerequisites', '基础要求'), ('how_to_start', '学习顺序'),
                       ('language', '语言'), ('access', '访问方式'),
                       ('scope', '适用范围'), ('applies_to', '适用范围'),
                       ('why_useful', '学习用途')]:
        text = resource_prose(resource.get(key, ''))
        if key == 'audience':
            text = text.replace('同济化学知识赛', '化学知识竞赛')
        if key in ('audience', 'prerequisites') and re.search(r'^相应赛事的|^对应专业基础', text):
            continue
        if text and text not in seen:
            parts.append((label + '：' if label else '') + text)
            seen.add(text)
    if resource.get('url'):
        parts.append('来源：' + resource['url'])
    return '\n'.join(dict.fromkeys(parts))


def prepare_resource(resource):
    """Turn private access notes into reader-facing learning descriptions."""
    row = dict(resource)
    for key in ('title', 'summary', 'audience', 'prerequisites', 'how_to_start',
                'language', 'scope', 'applies_to', 'why_useful'):
        row[key] = resource_prose(row.get(key, ''))
    if re.search(r'^对应学科竞赛|^该赛事备赛学生|^相应赛事', row['audience']):
        row['audience'] = ''
    if row['prerequisites'] == '先确认参加组别与资格':
        row['prerequisites'] = ''
    access = resource.get('access', '')
    if re.search(r'待确认|本机|已通过.*核对|需进入平台确认', access):
        row['access'] = ''
    else:
        row['access'] = resource_prose(access)
        row['access'] = re.sub(r'公开正式(?:来源|网页)', '公开阅读', row['access'])
        row['access'] = re.sub(r'；工具安装、课程视频与下载条件以提供方页面为准', '', row['access'])
    if row['summary'] in ('查看原文', '官方原通知转载') or not row['summary']:
        row['summary'] = row['why_useful'] or row['how_to_start']
    return row


def resource_prose(value):
    value = str(value or '').replace('可读取正文/附件', '在线阅读').replace('能读取', '介绍')
    if '已留存用户提供' in value:
        return '查看原文'
    parts = re.split(r'(?<=[。；;])', value)
    parts = [part for part in parts if not re.search(
        r'未登录读取|来源与目录身份差异|非赛事官方指定|不是本赛事获奖|不声称|不代替|不得当|'
        r'非12月现场版本|不等于.*指定平台|读取受限|读取受工具|访问条件需确认|现阶段.*加载失败|'
        r'不能据标题推断|后续赛程以最新通知为准|当前仍可报名|不适用于下一届|'
        r'不等同|并非比赛指定|不等于.*指定|不(?:是|属于).*指定|不是.*完整|'
        r'不复制参赛作品|不含(?:标准答案|裁判内部)|不要将|不把示例|回放不能替代|'
        r'不能推广|非.*赛制|^非.*教材|非.*参赛条件|不是2026|不作为.*要求|'
        r'不能用于认定|不能视为完整|不是整个|不能由|不能替代|非当前|不宜混用|'
        r'不是.*(?:真题|当届题|论文全文|规则)|不是日盈杯|不能当个人|不能代表目录|'
        r'需另核|另核|核验日期|当前报名规则未知|不提供统一答案保证|'
        r'需另看同济|不能代替同济|不等于允许|非完整技术规则|'
        r'语料片段不是|参赛包版本和体积以|现场演唱录制限制以|'
        r'具体桥梁指标仍以|裁定以该页|冲突尺寸不要|已免费取得附件|'
        r'同济资格通知', part)]
    text = clean_text(''.join(parts)).replace('明确适用于', '适用于')
    text = re.sub(r'^(?:公开正文|公开原通知|原通知PDF|PDF|正文|页面|官方主题通知|官方原通知转载)(?:给出|说明|明确说明|列出|列|介绍|提供)', '', text)
    text = re.sub(r'官方历史档案中可读取的|公开可读取的|可读的', '', text)
    text = text.replace('可读天然产物', '包含天然产物').replace('官方ZIP已归档', '官方ZIP下载')
    text = text.replace('34页PDF已归档', '34页PDF').replace('当前规则已为2027', '2027年规则')
    return text.strip('，；;。 ')


def source_record(source, locator=None, quote=''):
    url = source.get('url', '')
    if urlsplit(url).scheme not in ('http', 'https') or not urlsplit(url).netloc:
        return None
    checked = source.get('verified_at') or source.get('checked_on')
    if not checked:
        return None
    try:
        date.fromisoformat(checked[:10])
    except (ValueError, TypeError):
        return None
    title = clean_text(source.get('title', '')) or source.get('publisher') or source.get('provider') or urlsplit(url).netloc
    raw_locator = locator or source.get('locator', '')
    if re.search(r'直接页面正文空|正文(?:不可读|为空)|搜索可读取', raw_locator):
        return None
    loc = clean_text(raw_locator) or '正文'
    identity = 'ev-' + digest([url, loc])[:20]
    return {'id': identity, 'url': url, 'title': title, 'quote': quote,
            'locator': loc, 'verified_at': checked[:10]}


def supported_fields(edition, sources_by_id):
    fields, evidence, references = {}, {}, []
    for key, requirement in edition.get('requirements', {}).items():
        if key not in HARD_FIELDS | set(FIELD_LABELS) or not isinstance(requirement, dict):
            continue
        value = requirement.get('value')
        if value in (None, '', []):
            continue
        ids = requirement.get('source_ids') or [requirement.get('source_id')]
        valid = [sources_by_id[sid] for sid in ids if sid in sources_by_id
                 and not campus_selection_source(sources_by_id[sid])]
        if not valid:
            continue
        status = requirement.get('status')
        locator = requirement.get('locator', '')
        if status != 'verified':
            # Legacy generated mappings list all sources with no field-level
            # locator. Accept only values literally present in a sourced fact.
            valid_ids = {s['id'] for s in valid}
            matching = [f for f in edition.get('facts', []) if f.get('source_id') in valid_ids
                        and str(value) in public_fact(f.get('text', ''))]
            if not matching:
                continue
            locator = matching[0].get('locator', '')
            valid = [sources_by_id[matching[0]['source_id']]]
        if isinstance(value, str) and key not in ('registration_url', 'participation_type'):
            value = clean_text(value)
            if not value:
                continue
        if key.endswith('deadline') or key == 'registration_start':
            try:
                date.fromisoformat(value)
            except (TypeError, ValueError):
                continue
        if key == 'registration_url' and urlsplit(str(value)).scheme not in ('http', 'https'):
            continue
        if key in ('team_size_min', 'team_size_max') and (type(value) is not int or value < 1):
            continue
        refs = [source_record(source, locator) for source in valid]
        refs = [r for r in refs if r]
        if not refs:
            continue
        fields[key] = value
        evidence[key] = [r['id'] for r in refs]
        references.extend(refs)
    extracted, extracted_evidence, extracted_refs = fact_fields(edition, sources_by_id)
    for key, value in extracted.items():
        if key not in fields:
            fields[key] = value
            evidence[key] = extracted_evidence[key]
    references.extend(extracted_refs)
    if 'participation_type' not in fields and ('team_size_min' in fields or 'team_size_max' in fields):
        team_facts = [fact for fact in edition.get('facts', [])
                      if re.search(r'每队|团队报名|组队', public_fact(fact.get('text', '')))
                      and fact.get('source_id') in sources_by_id
                      and not campus_selection_source(sources_by_id[fact['source_id']])]
        personal = any(re.search(r'个人参赛|个人赛|个人报名|个人或', public_fact(fact.get('text', '')))
                       for fact in edition.get('facts', []))
        if team_facts and not personal:
            reference = source_record(sources_by_id[team_facts[0]['source_id']], team_facts[0].get('locator'))
            if reference:
                fields['participation_type'] = 'team'
                evidence['participation_type'] = [reference['id']]
                references.append(reference)
    if fields.get('eligibility'):
        education = education_from_eligibility(fields['eligibility'])
        if education:
            fields['education'] = education
            evidence['education'] = evidence['eligibility']
        else:
            fields.pop('education', None)
            evidence.pop('education', None)
        add_explicit_study_filters(fields, evidence)
    return fields, evidence, references


def add_explicit_study_filters(fields, evidence):
    """Extract literal course restrictions, including explicit open eligibility."""
    text = fields.get('eligibility', '')
    ids = evidence.get('eligibility', [])
    if not ids:
        return
    if '无专业限制' in text or '日语或非日语专业本科生' in text:
        fields['majors'] = ['不限专业']
        evidence['majors'] = ids
    elif re.search(r'德语专业(?:本科生|在校本科生)', text):
        fields['majors'] = ['德语']
        evidence['majors'] = ids
    if '年级不限' in text:
        fields['grades'] = ['不限年级']
        evidence['grades'] = ids


def education_from_eligibility(text):
    if re.search(r'不含|不包括|不接受|除外|分别|组别|研究生组|本科组|分之一|比例|以.*为主|非硕博', text):
        return []
    levels = []
    for label, pattern in [('本科', r'本科|本[、，]'), ('研究生', r'研究生|研[、，]'),
                           ('硕士', r'硕士'), ('博士', r'博士'),
                           ('专科', r'专科|高职高专|大专'), ('高中', r'高中'), ('初中', r'初中')]:
        if re.search(pattern, text):
            levels.append(label)
    return levels


CATEGORY_PATTERNS = [
    ('mathematical-modeling', r'数学建模'),
    ('artificial-intelligence', r'人工智能|嵌入式AI|AI\+'),
    ('automation-and-robotics', r'机器人|智能制造|智能无人|机械创新|工程实践|嵌入式芯片|电气电子|机械产品|机械工程'),
    ('transportation-and-automotive', r'汽车|方程式|交通|物流技术'),
    ('chemistry-and-materials', r'化学|化工|材料|电化学|SAMPE|复合'),
    ('environment-and-sustainability', r'节能减排|能源经济|海洋知识|地质|可持续|生态|环保'),
    ('civil-engineering', r'土木|结构设计|BIM|桥梁设计|工程结构'),
    ('architecture-and-planning', r'建筑|建造|城市设计|花园|景观|规划设计'),
    ('mathematics-and-physics', r'数学|物理|力学|光电|空间科学'),
    ('medicine-and-health', r'医学|生命科学|生物医|健康'),
    ('politics-and-social-sciences', r'法庭|法律|仲裁|刑事|公法|人道法|市场调查'),
    ('languages-and-humanities', r'英语|外语|跨文化|诵读|诵写|语言|人文'),
    ('computer-science', r'程序设计|计算机|软件|信息安全|信息通信|ICT|信息科技'),
    ('media-and-communication', r'数字媒体|摄影|影视|新闻|传播'),
    ('art-and-design', r'艺术|设计|广告|创意|成图'),
    ('innovation-and-entrepreneurship', r'创新|创业|创客|挑战杯'),
]
COMMON_ALIASES = {
    '2026002': ['挑战杯创业计划赛'], '2026006': ['iCAN'],
    '2026014': ['华为ICT', 'ICT'], '2026020': ['AIC'],
    '2026041': ['ACM', 'ICPC', 'ACM-ICPC'], '2026061': ['Robocon'],
    '2026068': ['NCDA', '未来设计师'], '2026074': ['全国大学生数学建模竞赛', '数模'],
    '2026092': ['大广赛'], '2026096': ['VEX'],
    '2026105': ['FDI Moot'], '2026106': ['Jessup'], '2026107': ['Vis Moot'],
    '2026108': ['ICC Moot'], '2026128': ['SCIP+'], '2026135': ['SCIP+'],
    '2026141': ['Swift Student Challenge'], '2026143': ['CCSP'],
    '2026173': ['FSEC'], '2026174': ['FSCC'], '2026175': ['FSAC'],
    '2026179': ['James Dyson Award', '戴森设计大奖'],
}


def add_discovery_metadata(record, allowed_categories):
    """Topic classification aids discovery and never populates major eligibility."""
    refs = [s['id'] for s in record['sources']]
    if not record.get('category'):
        for category, pattern in CATEGORY_PATTERNS:
            if category in allowed_categories and re.search(pattern, record['title'], re.I):
                record['category'] = category
                break
    if record.get('category'):
        record['category_evidence'] = refs[:1]
    aliases = list(record.get('aliases', []))
    aliases.extend(re.findall(r'（目录旧称：([^）]+)）', record['title']))
    record['title'] = re.sub(r'（目录旧称：[^）]+）', '', record['title'])
    aliases.extend(COMMON_ALIASES.get(record['catalog_code'], []))
    for term in re.findall(r'[（(]([A-Za-z][A-Za-z0-9 .+\-]{1,40})[）)]', record['title']):
        if not re.search(r'\d{4}', term):
            aliases.append(term)
    for term in re.findall(r'(?<![A-Za-z])[A-Z][A-Z0-9]{2,12}(?![A-Za-z])', record['title']):
        aliases.append(term)
    record['aliases'] = list(dict.fromkeys(alias for alias in aliases if alias and alias != record['title']))
    record['alias_evidence'] = {alias: refs[:1] for alias in record['aliases']}


def fact_fields(edition, sources_by_id):
    """Extract only explicit, single-scope statements from already sourced facts."""
    fields, evidence, references = {}, {}, []
    candidates = []
    for fact in edition.get('facts', []):
        source = sources_by_id.get(fact.get('source_id'))
        text = public_fact(fact.get('text', ''))
        if not source or campus_selection_source(source) or not text:
            continue
        ref = source_record(source, fact.get('locator'))
        if ref:
            candidates.append((text, ref))
    eligible = [(text, ref) for text, ref in candidates if re.search(
        r'参赛对象|参赛资格|面向.*(?:学生|本科|研究生)|在校(?:本科|研究|大学|学生)|在籍本科|在读本科|本科.*专科生|大学生组|全日制.*学生', text)
        and not re.search(r'推荐名额|每校|每个学校|每所学校', text)]
    if eligible:
        fields['eligibility'] = '\n'.join(dict.fromkeys(text for text, _ in eligible))
        evidence['eligibility'] = list(dict.fromkeys(ref['id'] for _, ref in eligible))
        references.extend(ref for _, ref in eligible)
        joined = '\n'.join(text for text, _ in eligible)
        # Exclusion syntax and different divisions require a richer rule model.
        # Keep the precise text but don't flatten them into demographic filters.
        if not re.search(r'不含|不包括|不得|不接受|不允许|除外|分别|组别|研究生组|本科组|分之一|比例|以.*为主|非硕博', joined):
            levels = [label for label in ('本科', '硕士', '博士', '专科', '高中', '初中') if label in joined]
            if '研究生' in joined:
                levels.extend(['硕士', '博士'])
            if levels:
                fields['education'] = list(dict.fromkeys(levels))
                evidence['education'] = evidence['eligibility']
    # Multiple numeric team rules often belong to different tracks. They remain
    # in prose unless all explicit team bounds agree.
    bounds = []
    for text, ref in candidates:
        if re.search(r'不同赛道|各赛道|本科组|研究生组|教师组|自由赛|企业赛|平面类|视频类', text):
            continue
        for match in re.finditer(r'(?:每队(?:学生)?|每支队伍|每个团队|团队|队伍)[^。；]{0,8}?(\d+)\s*[—–\-至~～]\s*(\d+)\s*(?:名|人)', text):
            bounds.append((int(match[1]), int(match[2]), ref))
        for match in re.finditer(r'(\d+)\s*[—–\-至~～]\s*(\d+)\s*人组队', text):
            bounds.append((int(match[1]), int(match[2]), ref))
        for match in re.finditer(r'每队(?:学生)?(?:最多|不超过|至多)\s*(\d+)\s*(?:名学生|名|人)', text):
            bounds.append((None, int(match[1]), ref))
        if re.search(r'个人或\d+\s*[—–\-至~～]\s*\d+\s*人组队', text):
            fields['participation_type'] = 'both'
            evidence['participation_type'] = [ref['id']]
            references.append(ref)
    distinct = {(low, high) for low, high, _ in bounds}
    if len(distinct) == 1:
        low, high = next(iter(distinct))
        ids = list(dict.fromkeys(ref['id'] for _, _, ref in bounds))
        if low is not None:
            fields['team_size_min'] = low
            evidence['team_size_min'] = ids
        fields['team_size_max'] = high
        evidence['team_size_max'] = ids
        references.extend(ref for _, _, ref in bounds)
    return fields, evidence, references


def build_edition_record(entry, edition):
    if entry.get('identity_status') == 'unconfirmed' or edition.get('evidence_status') not in ('rules', 'partial'):
        return None, 'identity_or_core_evidence'
    if not edition.get('year'):
        return None, 'edition_unspecified'
    if re.search(r'现有为外校校选|仅取得外校选拔|仍为同校遴选', '\n'.join(edition.get('gaps', []))):
        return None, 'campus_selection_only'
    source_map = {s['id']: s for s in edition.get('sources', []) if s.get('id')}
    sections, refs = [], []
    for index, fact in enumerate(edition.get('facts', []), 1):
        source = source_map.get(fact.get('source_id'))
        text = public_fact(fact.get('text', ''))
        if not source or campus_selection_source(source) or not text:
            continue
        reference = source_record(source, fact.get('locator'))
        if not reference:
            continue
        refs.append(reference)
        sections.append({'id': f'fact-{index}', 'heading': fact_heading(text, fact.get('locator', '')), 'text': text,
                         'evidence_ids': [reference['id']]})
    if not sections:
        return None, 'no_supported_public_fact'
    fields, field_evidence, field_refs = supported_fields(edition, source_map)
    refs.extend(field_refs)
    for field, value in fields.items():
        if field in FIELD_LABELS:
            sections.append({'id': 'field-' + field, 'heading': FIELD_LABELS[field],
                             'text': str(DISPLAY_VALUES.get(value, value)) if isinstance(value, (str, int)) else '、'.join(value),
                             'evidence_ids': field_evidence[field]})
    code = edition.get('competition_reference') or 'curated-' + edition['id']
    if entry.get('number') in (122, 123):
        code = 'curated-shanghai-mechanics-2026-7'
    category = entry.get('competition_category', {})
    if isinstance(category, dict):
        category = category.get('code', '')
    record = {'id': code, 'catalog_code': entry['code'], 'catalog_codes': [entry['code']],
              'competition_id': None, 'code': code,
              'title': entry.get('current_name') or entry['name'], 'edition': edition_label(edition['label']),
              'category': category or '', 'level': edition.get('fields', {}).get('level', 'unknown'),
              'aliases': [], 'summary': sections[0]['text'], 'fields': fields,
              'field_evidence': field_evidence,
              'sources': list({r['id']: r for r in refs}.values()), 'sections': sections,
              'review_status': 'approved', 'publication_status': 'published', 'kind': 'edition'}
    record['content_hash'] = digest(record)
    return record, None


OVERVIEW_REVISIONS = {
    '2026043': '计算机系统能力大赛考查系统实现能力；操作系统赛包含内核实现与功能挑战方向，CPU设计赛考查处理器设计。',
    '2026045': 'ISCC的信息安全对抗比赛包含破阵夺旗、无限擂台和数据安全赛，2026年按河南、上海、综合区域组织区域赛。',
    '2026047': '2026年大赛分11个作品大类，面向在籍本科生，经校赛、省赛推选参加国赛。',
    '2026049': '赛事以设计—建造一体化为核心，2026年在上海复兴岛举行，以竹竿与纸板围绕“你所定义的家”进行限时建造。',
    '2026051': '2026年题目为“何以栖居——城市、郊区与乡村”，关注社区关系、场所归属和可持续居住。参赛作品采用匿名图纸及视频展示。',
    '2026053': '2026年主题“美好生活HAI家园”关注AI与人的创造力协同，涵盖交通出行、居住、公共空间和文脉延续等城市设计场景。',
    '2026056': 'ARCASIA学生设计竞赛面向建筑设计创作，可结合历届学生作品研究建筑方案与图面表达。',
    '2026058': '赛事围绕交通运输领域开展科技创新，以项目作品说明技术方案及其成果。',
    '2026062': 'Formula SAE Japan由学生车队设计和制造赛车，分别设置电动与内燃机类别，车辆须满足赛事通用技术规则及日本赛的补充规则。',
    '2026065': '红点奖设产品设计、品牌与传达设计、设计概念三个独立赛事。Design Concept面向设计概念，Product Design面向已销售或近期量产的产品。',
    '2026066': '赛事设创意与定向主题两条赛道。创意赛道覆盖六个设计领域，定向赛道有16个主题。',
    '2026068': '赛事设非命题、产教融合与创新创业、公益、实践挑战等赛道，作品涵盖数字媒体、交互与产品设计等类别。',
    '2026074': '以实际问题为背景进行数学建模、计算和论文表达，参赛者通过模型假设、求解与检验形成论文。',
    '2026076': 'ASCE学生锦标赛包括混凝土独木舟、可持续方案和测量等土木工程项目，各项目分别设定任务。',
    '2026077': '2026年题目为《勒勒车模型结构设计与制作》，参赛训练包括结构方案、力学计算、模型制作及加载测试。',
    '2026082': '赛事由21世纪报社主办，设置青年组和大学组，评分包含内容、表达和综合印象。',
    '2026083': '赛事考查跨文化交际能力，训练跨文化情境分析、沟通表达与团队协作。',
    '2026085': '中国光学学会主办的光电类竞赛，2026年设创意设计、光学设计两个赛道；光学设计赛道按指定题目完成设计报告。',
    '2026088': '医学创新赛事设置实验设计和创新研究等作品类别，参赛者围绕所选学科准备研究说明与展示材料。',
    '2026089': '赛事面向数字媒体技术与创意作品，涵盖人工智能、虚拟现实、交互、数字艺术等方向。',
}
OVERVIEW_FACTS = {
    ('2026020', 1): '接受AI应用及开源贡献，要求实质改进；单纯调用接口或界面包装不足。',
    ('2026034', 1): '第十二届分为2026年常规赛和2027年数字孪生挑战赛。',
    ('2026051', 1): '每组至多4人。',
    ('2026054', 1): '参赛团队为3—7人，须完成花园建造与运维。',
    ('2026065', 1): '2027年产品设计奖早鸟阶段截至2026年10月9日。',
    ('2026066', 1): '创意赛道征集截至2026年11月27日17:00，定向主题截至2027年3月5日17:00。',
    ('2026089', 1): '报名及提交截止为2026年10月23日23:59:59。',
}


def build_overview_record(entry, checked_on):
    if entry['code'] in {'2026052', '2026057', '2026063', '2026064', '2026067'}:
        return None, 'identity_or_edition_scope'
    refs, sections = [], []
    readable = [source for source in entry.get('competition_sources', [])
                if source.get('verified_by') == 'page_read' and not campus_selection_source(source)]
    if entry['code'] == '2026020':
        readable = [source for source in readable if '/tracks-5/4924.html' in source['url']]
    overview = clean_text(entry.get('overview', ''))
    overview = OVERVIEW_REVISIONS.get(entry['code'], overview)
    if entry['code'] == '2026081':
        overview = '英语组设国际传播综合能力与笔译等赛项。'
    if not readable or not overview or re.search(r'^(?:官方)?(?:通知目录|资料目录|页面|首页|资料|通知)(?:同时保存|列出|提供|说明|介绍|明确)', overview):
        return None, 'no_supported_event_introduction'
    for source in readable:
        reference = source_record({**source, 'checked_on': checked_on}, '赛事介绍与通知正文')
        if reference:
            refs.append(reference)
    if refs:
        sections.append({'id': 'introduction', 'heading': '赛事介绍', 'text': overview,
                         'evidence_ids': [ref['id'] for ref in refs]})
    for index, source in enumerate(entry.get('competition_sources', []), 1):
        if source not in readable:
            continue
        # Source summaries describe the research process. Only reviewed factual
        # additions belong in reader-facing sections.
        text = OVERVIEW_FACTS.get((entry['code'], index), '')
        if not text:
            continue
        ref = source_record({**source, 'checked_on': checked_on}, '赛事介绍与通知正文')
        if ref:
            refs.append(ref)
            sections.append({'id': f'overview-{index}', 'heading': '赛事介绍', 'text': text,
                             'evidence_ids': [ref['id']]})
    if not sections:
        return None, 'no_read_source_body'
    code = 'm89-' + entry['code'] + '-overview'
    record = {'id': code, 'catalog_code': entry['code'], 'catalog_codes': [entry['code']],
              'competition_id': None, 'code': code, 'title': entry['name'],
              'edition': edition_label(re.split(r'[；;]', entry.get('edition_note', ''), maxsplit=1)[0]).rstrip('。'),
              'category': '', 'level': 'unknown', 'aliases': [], 'summary': sections[0]['text'],
              'fields': {}, 'field_evidence': {}, 'sources': refs, 'sections': sections,
              'kind': 'overview', 'review_status': 'approved', 'publication_status': 'published'}
    record['edition'] = {'2026008': '2027年·第十届', '2026025': '2026年Student Bridge',
                         '2026054': '2026年·社区花园赛道', '2026065': '赛事分类',
                         '2026078': '2022—2023赛季·第九届', '2026089': '2026年·第十四届'}.get(entry['code'], record['edition'])
    record['content_hash'] = digest(record)
    return record, None


def record_text(record):
    return '\n\n'.join([record['title'], record.get('edition', '')] +
                        [s['heading'] + '\n' + s['text'] for s in record['sections']])


def make_chunks(records, max_chars=700):
    chunks = []
    for record in records:
        for section in record['sections']:
            text = section['text']
            pieces = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
            for i, piece in enumerate(pieces):
                chunks.append({'id': record['id'] + ':' + section['id'] + ':' + str(i),
                               'record_id': record['id'], 'catalog_code': record['catalog_code'],
                               'title': record['title'], 'edition': record['edition'],
                               'heading': section['heading'], 'text': piece,
                               'evidence_ids': section['evidence_ids'],
                               'content_hash': digest(piece), 'record_hash': record['content_hash']})
    return chunks
