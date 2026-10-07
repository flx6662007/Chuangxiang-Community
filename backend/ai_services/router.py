"""Cost-free, deterministic intent routing. No user-provided URL is fetched."""

from dataclasses import dataclass
import re


DOMAIN_WORDS = {
    'competition': ('竞赛', '比赛', '赛事', '参赛', '报名', '大赛', 'competition', 'contest'),
    'project': ('科研', '课题', '实验室', '项目', '导师', 'research', 'project', 'lab'),
    'resource': ('资源', '教程', '课程', '学习资料', '工具', 'resource', 'tutorial'),
    'team': ('组队', '队友', '团队', '招募', 'team', 'teammate'),
}
MODES = ('smart', 'competition', 'research', 'resource')
WEB_WORDS = ('官网', '最新', '官方网站', '实时', '联网', '网上搜索', '网络搜索', '搜索网络', 'web', 'official site')
KNOWLEDGE_WORDS = ('资料', '规则', '章程', '指南', '怎么准备', '如何准备', '备赛', '要求', '文档')
TIME_WORDS = ('最新', '现在', '目前', '今年', '本届', '还可以', '截止', '报名中', '近期', '最近', 'today', 'current')
CONVERSATION_WORDS = ('你好', '嗨', '谢谢', '再见', '你是谁', '你能做什么', '帮我做什么',
                      '刚才', '上一轮', '之前的问题', '对话历史')


@dataclass(frozen=True)
class Route:
    intent: str
    domains: tuple[str, ...]
    current: bool
    web_requested: bool
    knowledge_requested: bool


def route_query(question, mode='smart'):
    if mode not in MODES:
        raise ValueError('invalid assistant mode')
    lowered = question.casefold()
    domains = tuple(name for name, words in DOMAIN_WORDS.items() if any(word in lowered for word in words))
    wants_web = any(word in lowered for word in WEB_WORDS)
    if mode == 'competition':
        domains = ('competition', 'resource')
    elif mode == 'research':
        domains = ('project', 'resource')
    elif mode == 'resource':
        domains = ('resource',)
    elif not domains:
        conversational = any(word in lowered for word in CONVERSATION_WORDS)
        domains = ('competition', 'project', 'resource') if not wants_web and not conversational and query_terms(question) else ('other',)
    wants_knowledge = any(word in lowered for word in KNOWLEDGE_WORDS)
    wants_platform = any(name in domains for name in ('competition', 'project', 'resource', 'team'))
    if wants_web and (wants_platform or wants_knowledge):
        intent = 'hybrid'
    elif wants_web:
        intent = 'web'
    elif wants_knowledge and wants_platform:
        intent = 'hybrid'
    elif wants_knowledge:
        intent = 'knowledge'
    elif wants_platform:
        intent = 'platform'
    else:
        intent = 'general'
    current = any(word in lowered for word in TIME_WORDS) or bool(re.search(r'(?<!\d)20\d{2}(?!\d)', lowered))
    return Route(intent, domains, current, wants_web, wants_knowledge)


def query_terms(question):
    """Keep topical terms only; a full natural-language sentence is not a DB search key."""
    reduced = question.casefold()
    for words in DOMAIN_WORDS.values():
        for word in words:
            reduced = reduced.replace(word, ' ')
    for word in WEB_WORDS + KNOWLEDGE_WORDS + TIME_WORDS + (
        '我想', '请问', '帮我', '推荐', '适合', '有没有', '有哪些', '怎么', '如何', '相关',
        '可以', '一个', '一些', '的', '吗', '呢', '是什么', '想了解', '学生', '本科',
    ):
        reduced = reduced.replace(word, ' ')
    return tuple(dict.fromkeys(token for token in re.findall(r'[\u4e00-\u9fff]{2,}|[a-z][a-z0-9+#.-]{1,}', reduced) if len(token) >= 2))[:8]
