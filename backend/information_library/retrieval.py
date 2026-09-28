"""未来 AI 助手的内部只读入口。没有 HTTP 路由、模型调用、向量库或网络请求。"""
from .selectors import KINDS, collect_records, knowledge_record


def search_knowledge(query='', *, kinds=None, limit=20):
    """返回带来源及状态的已发布内容；历史/待核实线索不能被解释为当前招募承诺。"""
    if not isinstance(query, str) or len(query) > 200:
        raise ValueError('关键词须为不超过 200 字符的文本。')
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError('limit 须为 1–50。')
    if kinds is not None and (not isinstance(kinds, (list, tuple))
                              or any(not isinstance(kind, str) or kind not in KINDS for kind in kinds)):
        raise ValueError('kinds 须为有效类型列表。')
    terms = query.casefold().split()
    result = []
    for row in collect_records(kinds, include_unpublished=False):
        searchable = (row['title'] + '\n' + row['text']).casefold()
        if row['_ai_ready'] and all(term in searchable for term in terms):
            result.append(knowledge_record(row))
        if len(result) >= limit:
            break
    return result
