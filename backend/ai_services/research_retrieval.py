"""Deterministic research intent and field matching; no inferred eligibility."""
import re

from .router import query_terms

RECRUIT_WORDS = ('招募', '招生', '申请', '参与', '加入', '实习', '兼职', '科研机会', '接收', '招收')
STOP_WORDS = ('介绍一下', '介绍下', '介绍', '了解一下', '想了解', '了解', '研究方向', '研究内容',
              '研究成果', '发表成果', '发表论文', '成果', '论文', '方向', '在研究什么', '研究什么',
              '附上来源', '附上链接', '附链接', '给我', '找一下', '找找', '查一下', '查找', '寻找',
              '推荐', '哪些', '有什么', '有没有', '有哪些', '一下', '现在', '目前', '历史', '过去',
              '以前', '已经结束', '已结束', '本科在读', '本科生', '本科实习生', '硕士生', '博士生',
              '硕士', '博士', '本科', '大一', '大二', '大三', '大四', '跨校', '校外', '外校',
              '申请条件', '招募对象', '申请资格', '时间投入', '每周', '工作内容', '做什么',
              '能不能', '是否', '有没有', '可以', '适合', '的', '吗', '呢', '我', '是', '请', '要', '想')


def intent(question):
    recruitment = any(word in question for word in RECRUIT_WORDS)
    level = ('undergraduate' if re.search(r'本科(?!学历|毕业)|大[一二三四]', question) else
             'postdoc' if '博士后' in question else 'master' if '硕士' in question else 'phd' if '博士' in question else '')
    introduction = any(w in question for w in ('介绍', '研究内容', '研究方向', '成果', '论文', '在研究'))
    recruitment = recruitment or bool(level) and not introduction
    return {'recruitment': recruitment, 'level': level if recruitment else '',
            'part_time': '兼职' in question, 'cross_school': any(w in question for w in ('跨校', '校外', '外校')),
            'historical': any(w in question for w in ('历史', '过去', '以前', '已结束')),
            'achievements': any(w in question for w in ('成果', '论文', '发表'))}


def topic_terms(question):
    reduced = question
    for word in sorted((*STOP_WORDS, *RECRUIT_WORDS, '实验室', '课题组', '科研', '研究', '招募信息'), key=len, reverse=True):
        reduced = reduced.replace(word, ' ')
    return query_terms(reduced)


def matches_conditions(row, request):
    facts = row.get('facts', {})
    if request['recruitment']:
        if request['historical']:
            if not row.get('has_recruitment_source') or row.get('recruitment_active'):
                return False
        elif not row.get('recruitment_active'):
            return False
    # Match admission targets, never research summary/reader audience or degree prerequisites.
    roles = facts.get('roles', '') or facts.get('eligibility', '')
    if request['level'] == 'undergraduate' and not re.search(r'本科生|本科在读|在读本科|本科实习|大[一二三四]', roles):
        return False
    if request['level'] == 'master' and not re.search(r'硕士生|硕士研究生|硕士(?!学历|学位|毕业)|(?<!博士)研究生', roles):
        return False
    if request['level'] == 'phd' and not re.search(r'博士生|博士研究生|博士(?!后|学历|学位|毕业)', roles):
        return False
    if request['level'] == 'postdoc' and '博士后' not in roles:
        return False
    if request['part_time']:
        commitment = roles + facts.get('commitment', '')
        if '兼职' not in commitment or re.search(r'不接受兼职|不支持兼职|不可兼职|不招兼职', commitment):
            return False
    if request['cross_school']:
        scope = facts.get('scope', '')
        if not scope or re.search(r'不接收|不接受|仅限|未说明|待确认', scope) or not re.search(r'跨校|校外|外校|全国高校|不限学校', scope):
            return False
    return True


def research_score(row, question, *, pinned=False):
    request = intent(question)
    if not pinned and not matches_conditions(row, request):
        return 0.0
    if pinned:
        return 1.0
    terms = topic_terms(question)
    facts = row.get('facts', {})
    title = (row['title'] + ' ' + row.get('institution', '')).casefold()
    body = '\n'.join(facts.values()).casefold() if facts else row['content'].casefold()
    # Exact topical phrases receive stronger weight than adjacent-character recall.
    scores = []
    for term in terms:
        if term in title:
            scores.append(1.0)
        elif term in body:
            scores.append(0.75)
        elif re.fullmatch(r'[\u4e00-\u9fff]{3,}', term):
            pairs = {term[i:i + 2] for i in range(len(term) - 1)}
            overlap = sum(pair in title + body for pair in pairs) / len(pairs)
            scores.append(overlap * 0.6 if overlap >= 0.65 else 0)
        else:
            scores.append(0)
    if terms:
        score = sum(scores) / len(scores)
        return score if score >= 0.25 else 0.0
    return 0.7 if request['recruitment'] or request['achievements'] and facts.get('achievements') else 0.0


def contextual_question(history, mode):
    """Resolve a bounded follow-up from user turns only, never client assistant text."""
    question = history[-1]['content']
    if mode not in ('research', 'smart') or len(history) < 3:
        return question
    if re.search(r'实验室|课题组|研究组', question):
        return question
    followup = re.search(r'^(那|它|这[个些家]|该[组实]|他们|还有|能否|是否|本科生|硕士生|博士生)', question)
    if not followup:
        return question
    for message in reversed(history[:-1]):
        if message['role'] == 'user' and re.search(r'实验室|课题组|研究组', message['content']):
            # Strip the previous request's eligibility constraints; latest question owns them.
            named = re.search(r'([\u4e00-\u9fffA-Za-z ]{2,40}(?:实验室|课题组|研究组))', message['content'])
            if named:
                topic = named.group(1)
                for prefix in ('介绍一下', '介绍', '请问', '我想了解', '了解一下'):
                    topic = topic.removeprefix(prefix)
                return topic.strip() + '：' + question
    return question
