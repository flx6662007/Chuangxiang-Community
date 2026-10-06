"""Shared competition retrieval for chat and the guided assistant."""
import os
from pathlib import Path

from information_library.competition_search import database_corpus, search_competitions
from information_library.semantic import build_index, save_index, SemanticError


def retrieve_knowledge(question, *, limit=4):
    result = search_competitions(query=question[:500], mode='hybrid', limit=limit)
    rows = []
    for hit in result['hits']:
        for passage in hit['passages']:
            for source in hit['evidence']:
                if source['id'] not in passage['evidence_ids']:
                    continue
                rows.append({
                    'kind': 'knowledge', 'entity_id': hit['record_id'],
                    'version': hit['content_hash'], 'content_hash': hit['content_hash'],
                    'title': hit['title'], 'edition': hit['edition'], 'url': source['url'],
                    'text': passage['text'], 'locator': source.get('locator'),
                    'verified_at': source.get('verified_at'), 'published_on': None,
                    'status': 'published', 'status_note': hit['edition'] or '赛事资料',
                    'internal_url': None,
                })
    return rows, ('ready' if rows else 'no_published_knowledge')


def rebuild_index(*, path=None, encoder=None):
    destination = path or os.getenv('COMPETITION_SEMANTIC_INDEX')
    if not destination:
        raise SemanticError('请设置 COMPETITION_SEMANTIC_INDEX 或传入 --output。')
    index = build_index(database_corpus(), encoder=encoder)
    target = Path(destination)
    temporary = target.with_name(target.name + '.building')
    try:
        save_index(index, temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return len(index.metadata['chunks'])
