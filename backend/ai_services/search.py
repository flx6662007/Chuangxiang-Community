"""在当前公开目录与知识正文中检索；不调用模型或外部网站。"""
import re
from collections import defaultdict

from django.db.models import Prefetch
from rest_framework.exceptions import ValidationError

from competition_catalog.api_selectors import catalog_counts
from competition_catalog.api_serializers import CatalogSerializer
from competition_catalog.models import CatalogEntry
from curation.models import DocumentLink
from curation.selectors import visible_documents
from information_library.presentation import reading_text
from information_library.selectors import public_text


# 同义词只扩展检索文本，不据此判断参赛资格或赛事是否正在报名。
SYNONYMS = (
    ('人工智能', ('人工智能', 'artificial intelligence', 'ai')),
    ('数学建模', ('数学建模', 'mathematical modeling', 'mathematical modelling')),
    ('程序设计', ('程序设计', '编程', 'programming')),
    ('RoboMaster', ('robomaster', '机甲大师')),
)
KNOWN_TERMS = ('机器学习', '深度学习', '计算机', '机器人', '物理', '化学', '生物',
               '机械', '电子', '建筑', '设计', '金融', '英语', '创新创业', '科研',
               'Python', 'C++', 'Java', '算法', '数据分析')
NOISE = re.compile(
    r'我(?:是|想|希望|会|对)?|帮我|给我|请|推荐|寻找|查找|查询|搜索|想找|找(?:一?个)?|'
    r'感兴趣|感兴?趣|会一点|一点|相关|有关|关于|适合|能够|可以|最好|希望|想要|想|'
    r'参加|报名|参赛|比赛|赛事|竞赛|专业|学生|同学|本科生|大[一二三四五六]|'
    r'[一二三四五六]年级|近期|最近|目前|现在|学习资料|有什么|有没有|一些|一个|哪些|什么|'
    r'组队|队友|团队|个人|入门|的|和|与|对|会|了|呢|吧|吗'
)


def _contains(text, term):
    """短拉丁词按边界匹配，避免 AI 命中 training 等单词。"""
    if re.fullmatch(r'[a-z0-9+]+', term):
        return re.search(r'(?<![a-z0-9])' + re.escape(term) + r'(?![a-z0-9])', text) is not None
    return term in text


def query_terms(query):
    remaining = public_text(query).casefold()
    terms = []
    for label, alternatives in SYNONYMS:
        if any(_contains(remaining, word) for word in alternatives):
            terms.append((label, alternatives))
            for word in alternatives:
                pattern = (r'(?<![a-z0-9])' + re.escape(word) + r'(?![a-z0-9])'
                           if re.fullmatch(r'[a-z0-9+]+', word) else re.escape(word))
                remaining = re.sub(pattern, ' ', remaining)
    for word in KNOWN_TERMS:
        term = word.casefold()
        if _contains(remaining, term):
            terms.append((word, (term,)))
            remaining = re.sub(r'(?<![a-z0-9])' + re.escape(term) + r'(?![a-z0-9])', ' ', remaining)
    remaining = NOISE.sub(' ', remaining)
    # 保留领域词表之外的词，如“天文学”“无人机”，避免只有预设主题能搜索。
    for word in re.findall(r'[a-z0-9][a-z0-9+#.-]*|[\u4e00-\u9fff]+', remaining):
        if len(word) >= 2 and not any(word == label.casefold() for label, _ in terms):
            terms.append((word, (word,)))
    return terms[:12]


def search_catalog(query):
    if not isinstance(query, str) or not query.strip():
        raise ValidationError({'q': '请输入赛事名称、方向或技能。'})
    if len(query) > 500:
        raise ValidationError({'q': '搜索内容最多 500 字符。'})
    query = query.strip()
    terms = query_terms(query)
    payload = {'mode': 'keyword', 'query': query, 'keywords': [label for label, _ in terms],
               'count': 0, 'results': []}
    if not terms:
        return payload

    entries = list(CatalogEntry.objects.filter(is_active=True).exclude(
        code__startswith='demo-').exclude(name__contains='【虚构样例】').order_by('code'))
    ids = [entry.pk for entry in entries]
    documents = visible_documents().exclude(code__startswith='demo-').exclude(
        current_revision__title__contains='【虚构样例】').exclude(
        current_revision__links__competition__code__startswith='demo-').exclude(
        current_revision__links__competition__title__contains='【虚构样例】').exclude(
        current_revision__links__resource__code__startswith='demo-').exclude(
        current_revision__links__resource__title__contains='【虚构样例】').filter(
        current_revision__links__catalog_id__in=ids).distinct().prefetch_related(Prefetch(
            'current_revision__links', queryset=DocumentLink.objects.filter(catalog_id__in=ids),
            to_attr='search_catalog_links'))
    document_hits = defaultdict(set)
    for document in documents:
        revision = document.current_revision
        metadata = revision.metadata if isinstance(revision.metadata, dict) else {}
        gaps = metadata.get('gaps', [])
        # 与前端详情使用相同的公开正文：联系行、内部处理说明不参与匹配。
        body = reading_text(revision.body, gaps=gaps if isinstance(gaps, list) else []).casefold()
        title = public_text(revision.title).casefold()
        matched = {label for label, words in terms if any(_contains(title + '\n' + body, word) for word in words)}
        for link in revision.search_catalog_links:
            document_hits[link.catalog_id].update(matched)

    ranked = []
    for entry in entries:
        title = public_text(entry.name).casefold()
        title_hits = {label for label, words in terms if any(_contains(title, word) for word in words)}
        if any(entry.code == word for _, words in terms for word in words):
            title_hits.add(entry.code)
        text_hits = document_hits[entry.pk] - title_hits
        if not title_hits and not text_hits:
            continue
        reasons = []
        for label, _ in terms:
            if label in title_hits:
                reasons.append(f'目录名称：{label}')
            elif label in text_hits:
                reasons.append(f'公开资料：{label}')
        ranked.append((len(title_hits | text_hits), len(title_hits), entry, '；'.join(reasons)))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2].code))
    selected = ranked[:8]
    counts = catalog_counts([item[2] for item in selected])
    payload['count'] = len(ranked)
    payload['results'] = [
        {'catalog': CatalogSerializer(entry, context={'counts': counts}).data, 'match_reason': reason}
        for _, _, entry, reason in selected
    ]
    return payload
