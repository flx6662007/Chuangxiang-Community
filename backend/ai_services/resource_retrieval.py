"""Local lexical resource matching, including public names and associations.

English names use token boundaries. Chinese short phrases are weighted by their
corpus frequency so conversational wording need not match a whole sentence.
No alias grants publication permission or fabricates a resource relationship.
"""

from collections import Counter
import math
import re


ENGLISH = re.compile(r'[a-z][a-z0-9]*(?:[+#]{1,2}|(?:[.-][a-z0-9]+)*)', re.I)
GENERIC = ('学习资料', '学习资源', '入门教程', '基础教程', '官方教程', '公开课程',
           '相关资料', '推荐资料', '资料入口', '站内入口', '站内资料', '参考资料',
           '课程介绍', '资源介绍', '学习材料', '怎么学习', '如何学习', '提供支持',
           '请帮我', '有没有', '有哪些', '我想', '可以', '工具', '教程', '课程',
           '入门', '基础', '官方', '学习', '资料', '资源', '平台', '介绍', '入口')
RULE_WORDS = ('规则', '规程', '章程', '报名指南', '报名通知', '邀请函', '技术规则')
MATERIAL_WORDS = ('资料', '资源', '教程', '课程', '文档', '指南', '规程', '规则文件',
                  '工具', '插件', '技能', '例程', '示例', '习题', '题库', '赛题', '附件', '论文',
                  '作业', '解答')
ENGLISH_STOP = {'ai', 'vr', 'ar', 'the', 'and', 'or', 'for', 'with', 'of', 'to', 'in'}
IDENTIFIER = re.compile(r'(?<![a-z0-9])(?:[a-z]{2,}\d{2,}[a-z]?|\d{1,3}\.\d{2,})(?![a-z0-9])', re.I)
PROBLEM_WORDS = re.compile(r'赛题|题目|试题|真题|样题|题库|习题|题集|作业|[一二三四五六七八九十\d]+题|problems|assignments', re.I)


def resource_request(question):
    return any(word in question.casefold() for word in MATERIAL_WORDS)


def resource_primary_request(question):
    """Material requests select resources; explicitly mixed requests keep domains.

    A contest mentioned as preparation context does not request contest cards.
    Research/contest comparisons and lists such as "比赛和学习资料" still do.
    """
    if not resource_request(question):
        return False
    # Papers can describe a lab's research output rather than requested study
    # material. Only suppress the paper-only trigger; explicit tools, courses,
    # plugins and other materials retain their resource scope.
    if ('论文' in question and re.search(r'科研|课题|实验室|导师|发表|成果', question) and
            not any(word in question for word in MATERIAL_WORDS if word != '论文')):
        return False
    if (re.search(r'科研|课题|实验室|研究机会', question) and
            re.search(r'竞赛|比赛|赛事', question)):
        return False
    domain = r'(?:科研机会|科研项目|课题组|实验室|导师|比赛|竞赛|赛事|团队|队友)'
    if re.search(domain + r'\s*(?:和|与|及|、|以及)', question):
        return False
    if re.search(r'(?:推荐|寻找|找|有哪些|比较|对比)[^，。；!?！？]{0,16}' + domain +
                 r'(?=[，。；!?！？]|$)', question):
        return False
    return True


def _identifiers(text):
    return {match.group().casefold() for match in IDENTIFIER.finditer(text)}


def _grams(text):
    return {part[i:i + size] for part in re.findall(r'[\u4e00-\u9fff]+', text)
            for size in (2, 3, 4) for i in range(len(part) - size + 1)}


STOP_GRAMS = set().union(*(_grams(word) for word in GENERIC))


def _english(text):
    terms = {match.group().casefold() for match in ENGLISH.finditer(text)}
    # An explicitly cased product name can supply its abbreviation: RoboMaster
    # -> RM. Never derive RM from an arbitrary substring such as Formula/ARM64.
    for word in re.findall(r'[A-Za-z][A-Za-z0-9]*', text):
        pieces = re.findall(r'[A-Z][a-z]+', word)
        if len(pieces) >= 2 and ''.join(pieces) == word:
            terms.add(''.join(piece[0] for piece in pieces).casefold())
    # Board identifiers remain meaningful despite being one Latin letter.
    terms.update(match.casefold() for match in re.findall(r'开发板\s*([A-Za-z])\s*型', text))
    return terms


def _terms(text):
    return (_grams(text) - STOP_GRAMS) | (_english(text) - ENGLISH_STOP)


def _association_text(row):
    return ' '.join([*(entry['title'] for entry in row.get('named_associations', [])),
                     *(value for entry in row.get('catalogs', [])
                       for value in [entry['name'], *entry.get('aliases', [])])])


def _navigation_targets(rows, question):
    """Only a title plus navigation wording is an exact resource lookup.

    Remaining functional terms (export, diagnostics, etc.) keep alternatives
    eligible even when a short product title occurs verbatim in the question.
    """
    compact = re.sub(r'\s+', '', question).casefold()
    targets = set()
    for row in rows:
        title = re.sub(r'\s+', '', row['title']).casefold()
        if len(title) < 2 or title not in compact:
            continue
        residual = compact.replace(title, '')
        for word in ('请帮我', '帮我', '找一下', '给我', '提供', '发我', '平台', '站内',
                     '请问', '哪里', '在哪', '有没有', '介绍', '入口', '链接', '这个',
                     '一下', '请', '找', '有', '的', '和', '吗', '呢'):
            residual = residual.replace(word, '')
        if not _terms(residual):
            targets.add(row['object_id'])
    return targets


def _mentioned_catalogs(rows, question):
    """Resolve event names from actual public aliases and cup names in titles.

    Resource titles can carry a cup name absent from the catalog's formal name.
    Such a name contributes only its already-established catalog relationships.
    """
    question_english = _english(question)
    mentions = {}
    for row in rows:
        catalogs = row.get('catalogs', [])
        for entry in catalogs:
            names = [entry['name'], *entry.get('aliases', [])]
            matches = {name for name in names if len(name) >= 2 and
                       ((name.isascii() and name.casefold() in question_english) or
                        (not name.isascii() and name.casefold() in question.casefold()))}
            matches.update(term for name in names for term in _english(name) - ENGLISH_STOP
                           if len(term) > 1 and term in question_english)
            # A cup name must be a contiguous literal phrase in both the query
            # and the public title; never infer a catalog from topical similarity.
            for name in [row['title'], *names]:
                for prefix in re.findall(r'[\u4e00-\u9fff]{2,16}杯', name):
                    matches.update(prefix[-size:] for size in range(3, len(prefix) + 1)
                                   if prefix[-size:] in question)
            for match in matches:
                mentions.setdefault(match, set()).add(entry['code'])
    # Prefer the most specific literal mention over any shorter substring.
    return set().union(*(codes for name, codes in mentions.items()
                         if not any(name != other and name in other for other in mentions))) if mentions else set()


def relevant_resource_ids(keyword, semantic):
    """Admission depends on query relevance, before trust/freshness bonuses.

    Keep multiple substantive keyword matches. A purely semantic fallback is
    allowed when no substantial keyword match exists; otherwise it must be a
    strong match in its own right, not just a generic neighboring topic.
    """
    best_keyword = max(keyword.values(), default=0)
    best_semantic = max(semantic.values(), default=0)
    keyword_floor = max(.18, best_keyword * .45)
    semantic_floor = max(.72 if best_keyword >= .18 else .60, best_semantic - .05)
    return {identifier for identifier in keyword.keys() | semantic.keys()
            if keyword.get(identifier, 0) >= keyword_floor or
            semantic.get(identifier, 0) >= semantic_floor}


def resource_scores(records, question):
    """Return independent keyword scores and semantic eligibility.

    An explicit English name still excludes unrelated semantic candidates, but
    a course can satisfy a competition name through its actual public links.
    Structured identifiers form a separate gate: a matching language/tool name
    cannot substitute for a specifically requested course. Alternatives within
    either group remain a union so comparisons can retrieve multiple courses.
    """
    rows = [row for row in records if row['object_type'] == 'resource']
    if not rows:
        return {}, set()
    positive = re.sub(r'(?:不要|不需要|不看|排除)[^，。；!?！？]*', '', question)
    query_english = _english(positive) - ENGLISH_STOP
    # Standalone a/i are usually prose, except an explicit board/language name.
    query_english = {term for term in query_english if len(term) > 1 or
                     re.search(r'(?<![a-z0-9])' + re.escape(term) + r'\s*(?:板|语言|程序)', positive, re.I)}
    query_identifiers = _identifiers(positive)
    navigation_targets = _navigation_targets(rows, positive)
    catalog_scope = _mentioned_catalogs(rows, positive)
    wants_rules = any(word in positive for word in RULE_WORDS)
    wants_problems = bool(re.search(r'赛题|真题|样题|题库|题目(?:附件|文件)', positive))
    wants_learning = bool(re.search(r'教程|课程|学习|练习|习题|语法|入门|上手|例程|示例|作业|解答', positive)) and not wants_rules
    excluded = ' '.join(re.findall(r'(?:不要|不需要|不看|排除)([^，。；!?！？]*)', question))
    excludes_rules = bool(re.search(r'规则|规程|章程|报名|通知|邀请函', excluded))
    years = set(re.findall(r'(?<!\d)20\d{2}(?!\d)', positive)) if wants_problems or wants_rules else set()
    fields = {}
    frequencies = Counter()
    for row in rows:
        title = _terms(row['title'])
        body_text = ' '.join([row['summary'], row['content'], *row['tags'], *row['direction']])
        body = _terms(body_text)
        associations = _terms(_association_text(row))
        english = _english(row['title'] + ' ' + body_text + ' ' + _association_text(row))
        identifiers = _identifiers(row['title'] + ' ' + body_text)
        fields[row['object_id']] = (title, body, associations, english, identifiers)
        frequencies.update(title | body | associations)
    query = _terms(positive)
    known = query & frequencies.keys()
    weights = {term: (1 + math.log((len(rows) + 1) / (frequencies[term] + 1))) *
               (1.5 if term.isascii() else len(term) / 2) for term in known}
    total = sum(weights.values()) or 1
    scores, eligible = {}, set()
    for row in rows:
        if navigation_targets and row['object_id'] not in navigation_targets:
            continue
        if catalog_scope and not catalog_scope & {entry['code'] for entry in row.get('catalogs', [])}:
            continue
        is_rules = any(word in row['title'] for word in (*RULE_WORDS, '通知'))
        if is_rules and (excludes_rules or wants_learning or wants_problems) and not wants_rules:
            continue
        if wants_problems and not PROBLEM_WORDS.search(row['title'] + ' ' + row['summary']):
            continue
        document_years = set(re.findall(r'(?<!\d)20\d{2}(?!\d)', row['title'] + ' ' + row['summary']))
        if years and document_years and not years & document_years:
            continue
        title, body, associations, english, identifiers = fields[row['object_id']]
        if query_identifiers and not query_identifiers & identifiers:
            continue
        if query_english and not query_english & english:
            continue
        eligible.add(row['object_id'])
        matches = known & (title | body | associations)
        if not matches:
            continue
        coverage = sum(weights[term] * (1.0 if term in title or term in body else .65)
                       for term in matches) / total
        title_coverage = sum(weights[term] for term in known & title) / total
        score = .78 * coverage + .22 * title_coverage
        compact_title = re.sub(r'\s+', '', row['title']).casefold()
        if compact_title and compact_title in re.sub(r'\s+', '', positive).casefold():
            score += .16
        if wants_rules:
            score *= 1.2 if is_rules else .45
        elif wants_learning and is_rules:
            score *= .3
        # Mere shared boilerplate or a short Chinese overlap cannot create a hit.
        if score >= .08:
            scores[row['object_id']] = min(1.0, score)
    return scores, eligible


def association_priority(name, question):
    """Query-related names first, retaining every validated association."""
    query = _terms(question)
    return -len(query & _terms(name)), name
