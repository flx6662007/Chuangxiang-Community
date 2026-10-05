"""Read only public, verified platform records; never use frontend mock data."""

from information_library.selectors import collect_records, public_text, safe_source_url
from resources.models import Resource

from .router import query_terms


def _score(text, terms):
    folded = text.casefold()
    return sum(1 for term in terms if term in folded)


def retrieve_platform(question, route, *, limit=5):
    terms = query_terms(question)
    items = []
    kinds = []
    if 'competition' in route.domains:
        kinds.append('competition')
    if 'project' in route.domains:
        kinds.append('research')
    if kinds:
        for row in collect_records(kinds):
            if not row['source_urls']:
                continue
            score = _score(row['title'] + ' ' + row['text'], terms)
            if terms and not score:
                continue
            url = row['source_urls'][0]
            entity_id = row['id']
            # Only competition has a real public detail page. Research JSON is a lead, not a site entity.
            internal = (f'/competitions/{entity_id[3:]}' if row['kind'] == 'competition'
                        and entity_id.startswith('db-') else None)
            items.append({
                'kind': row['kind'], 'entity_id': entity_id, 'version': row['version'],
                'title': row['title'], 'url': url, 'internal_url': internal,
                'text': row['text'][:1800], 'verified_at': row['verified_at'],
                'published_on': next((date['published_on'] for date in row['source_dates']
                                      if date['url'] == url), None),
                'status': row['content_status'], 'status_note': row['status_note'],
                '_score': score,
            })
    if 'resource' in route.domains:
        rows = Resource.objects.filter(publication_status='published', availability='available',
                                       last_verified_at__isnull=False).order_by('-last_verified_at')[:100]
        for row in rows:
            url = safe_source_url(row.access_url)
            if not url or row.title.startswith('【虚构样例】') or row.code.startswith('demo-'):
                continue
            score = _score(row.title + ' ' + row.description, terms)
            if terms and not score:
                continue
            items.append({
                'kind': 'resource', 'entity_id': str(row.pk), 'version': str(row.content_version),
                'title': public_text(row.title), 'url': url, 'internal_url': None,
                'text': public_text(row.description)[:1800],
                'verified_at': row.last_verified_at.isoformat(), 'published_on': None,
                'status': 'available', 'status_note': '资源链接已核验；可用性以原站当前状态为准。',
                '_score': score,
            })
    items.sort(key=lambda item: (item['_score'], item['verified_at'] or ''), reverse=True)
    return [{key: value for key, value in item.items() if key != '_score'} for item in items[:limit]]
