"""Public, typed retrieval and relation expansion for the single chat assistant."""

from datetime import datetime, timezone as dt_timezone
import re

from django.conf import settings
from django.utils import timezone

from information_library.competition_search import search_competitions
from information_library.selectors import collect_records, public_text, safe_source_url
from information_library.semantic import SemanticError
from research.models import ResearchOpportunity
from resources.models import Resource, ResourceCompetition, ResourceResearchOpportunity

from .router import query_terms
from .platform import retrieve_platform
from .unified_index import search as semantic_search
from .research_retrieval import intent as research_intent, research_score, matches_conditions


class ResearchGroupSelector:
    """Future DB owner can supply public, reviewed group records with this schema.

    Required: object_type='research_group', object_id, title, summary,
    content, source_url, verified_at, version, status='published'. Optional:
    published_at, tags, category, direction, related_object_ids. Relations
    must use real foreign keys; no group is inferred from free text.
    """

    def public_records(self):
        return []


DEFAULT_WEIGHTS = {
    'keyword': 0.32, 'semantic': 0.27, 'mode': 0.13,
    'source': 0.10, 'freshness': 0.06, 'relation': 0.12,
}
RANK_BASELINES = {'competition_hybrid': 0.82, 'competition_keyword': 0.76,
                  'competition_exact_bonus': 0.12, 'competition_rank_step': 0.02,
                  'direct_competition': 0.72}


def retrieval_weights():
    configured = getattr(settings, 'AI_RETRIEVAL_WEIGHTS', {})
    if not isinstance(configured, dict):
        return DEFAULT_WEIGHTS
    weights = {**DEFAULT_WEIGHTS, **{key: value for key, value in configured.items()
                                   if key in DEFAULT_WEIGHTS and type(value) in (int, float) and 0 <= value <= 1}}
    total = sum(weights.values()) or 1
    return {key: value / total for key, value in weights.items()}


def rank_baselines():
    configured = getattr(settings, 'AI_RETRIEVAL_BASELINES', {})
    if not isinstance(configured, dict):
        return RANK_BASELINES
    return {**RANK_BASELINES, **{key: value for key, value in configured.items()
                               if key in RANK_BASELINES and type(value) in (int, float) and 0 <= value <= 1}}


def _record(kind, identifier, title, summary, content, url, *, source_type='platform',
            published_at=None, verified_at=None, version='', status='published',
            tags=(), category='', direction=(), related=None, group_label=''):
    related = {key: [identifier for identifier in values if isinstance(identifier, str)]
               for key, values in (related or {}).items() if isinstance(key, str) and isinstance(values, list)}
    return {
        'object_type': kind, 'object_id': str(identifier), 'title': public_text(title),
        'summary': public_text(summary), 'content': public_text(content),
        'tags': [public_text(value) for value in tags if isinstance(value, str)],
        'category': public_text(category),
        'direction': [public_text(value) for value in direction if isinstance(value, str)],
        'source_url': safe_source_url(url), 'source_type': source_type,
        'published_at': published_at, 'verified_at': verified_at,
        'version': str(version), 'status': status, 'related_object_ids': related,
        'research_group_label': public_text(group_label), 'retrieval_score': 0.0,
    }


def public_secondary_records(*, group_selector=None):
    """Resource and research only. Competition keeps its evidence-aware retriever."""
    rows = []
    public_resources = Resource.objects.filter(publication_status='published', availability='available').exclude(
        code__startswith='demo-').exclude(title__contains='【虚构样例】').select_related('category').prefetch_related(
        'tags', 'directions').order_by('code')
    resource_ids = list(public_resources.values_list('pk', flat=True))
    competition_links = {}
    for resource_id, competition_id in ResourceCompetition.objects.filter(
            resource_id__in=resource_ids, competition__publication_status='published').values_list('resource_id', 'competition_id'):
        competition_links.setdefault(resource_id, []).append(f'db-{competition_id}')
    research_links = {}
    if settings.PUBLIC_RESEARCH_ENABLED:
        for resource_id, opportunity_id in ResourceResearchOpportunity.objects.filter(
                resource_id__in=resource_ids, opportunity__publication_status='published').values_list('resource_id', 'opportunity_id'):
            research_links.setdefault(resource_id, []).append(f'db-{opportunity_id}')
    for item in public_resources:
        url = safe_source_url(item.access_url)
        if not url:
            continue
        rows.append(_record('resource', item.code, item.title, item.description[:500], item.description, url,
                            source_type='platform_resource', published_at=item.published_at.isoformat() if item.published_at else None,
                            verified_at=item.last_verified_at.isoformat() if item.last_verified_at else None,
                            version=item.content_version, category=item.category.name if item.category else '',
                            tags=[term.name for term in item.tags.all()], direction=[term.name for term in item.directions.all()],
                            related={'competition': competition_links.get(item.pk, []),
                                     'research_opportunity': research_links.get(item.pk, [])}))
    if settings.PUBLIC_RESEARCH_ENABLED:
        opportunities = {f'db-{item.pk}': item for item in ResearchOpportunity.objects.filter(
            publication_status='published').exclude(code__startswith='demo-')}
        # collect_records enforces source verification, withdrawal, public-text and editorial boundaries.
        for source in collect_records(['research']):
            if not source['source_urls'] or not source.get('_ai_ready'):
                continue
            item = opportunities.get(source['id'])
            related = {'resource': list(ResourceResearchOpportunity.objects.filter(
                opportunity=item, resource__publication_status='published', resource__availability='available'
            ).values_list('resource__code', flat=True))} if item else {}
            rows.append(_record('research_opportunity', source['id'], source['title'], source['text'][:500],
                                source['text'], source['source_urls'][0], source_type='platform_research',
                                published_at=source.get('source_published_on'), verified_at=source['verified_at'],
                                version=source['version'] or '', status=source['publication_status'], related=related,
                                group_label=item.research_group if item else ''))
            rows[-1]['status_note'] = source['status_note']
            rows[-1]['content_status'] = source['content_status']
            rows[-1].update({key: source[key] for key in (
                'institution', 'facts', 'field_links', 'evidence_blocks', 'has_recruitment_source',
                'recruitment_active') if key in source})
            if source.get('facts'):
                rows[-1]['summary'] = source['facts'].get('summary', source['title'])
        selector = group_selector or ResearchGroupSelector()
        for row in selector.public_records():
            if (isinstance(row, dict) and all(isinstance(row.get(key), str) and row[key].strip()
                                             for key in ('object_id', 'title', 'summary', 'content', 'version'))
                    and row.get('object_type') == 'research_group' and row.get('status') == 'published'
                    and isinstance(row.get('verified_at'), str) and row['verified_at']
                    and safe_source_url(row.get('source_url'))):
                rows.append(_record('research_group', row['object_id'], row['title'], row['summary'],
                                    row['content'], row['source_url'], source_type='platform_research',
                                    published_at=row.get('published_at'), verified_at=row['verified_at'],
                                    version=row['version'], tags=row.get('tags', []),
                                    category=row.get('category', ''), direction=row.get('direction', []),
                                    related=row.get('related_object_ids', {})))
        visible_research = {row['object_id'] for row in rows
                            if row['object_type'] == 'research_opportunity'}
        for row in rows:
            if row['object_type'] == 'resource':
                row['related_object_ids']['research_opportunity'] = [identifier for identifier in
                    row['related_object_ids'].get('research_opportunity', []) if identifier in visible_research]
    return rows


def _keyword_score(row, question, terms):
    title, body = row['title'].casefold(), (row['summary'] + ' ' + row['content'] + ' ' +
        ' '.join(row['tags']) + ' ' + row['category'] + ' ' + ' '.join(row['direction'])).casefold()
    exact = question.casefold().strip() == title
    matches = sum(3 if term in title else 1 if term in body else 0 for term in terms)
    return min(1.0, (0.65 if exact else 0) + matches / max(3, len(terms) * 2))


def _freshness(row):
    value = row['verified_at'] or row['published_at']
    if not value:
        return 0.0
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=dt_timezone.utc)
        days = max(0, (timezone.now() - stamp).days)
        return max(0.0, 1 - days / 365)
    except (ValueError, TypeError):
        return 0.0


def _mode_fit(kind, mode):
    return 1.0 if (mode == 'smart' or (mode == 'competition' and kind == 'competition')
                   or (mode == 'research' and kind in ('research_opportunity', 'research_group'))
                   or (mode == 'resource' and kind == 'resource')) else 0.35


def _rank(rows, question, mode, *, index=None):
    terms = query_terms(question)
    # Explicit technology names are topical anchors; shared words like 入门 cannot replace them.
    anchors = [term for term in re.findall(r'[a-z][a-z0-9+#.-]{1,}', question.casefold())
               if term not in ('ai', 'vr', 'ar')]
    research_request = research_intent(question)
    research_rows = [row for row in rows if row['object_type'] == 'research_opportunity']
    pinned = {row['object_id'] for row in research_rows if row['title'] in question}
    # School restrictions are explicit only when the query names a known institution.
    schools = {row['institution'].split(' · ')[0] for row in research_rows
               if row.get('institution') and row['institution'].split(' · ')[0] in question}
    def eligible(row):
        if row['object_type'] == 'resource' and anchors:
            text = ' '.join((row['title'], row['summary'], row['content'], *row['tags'], *row['direction'])).casefold()
            if not all(anchor in text for anchor in anchors):
                return False
        if row['object_type'] != 'research_opportunity':
            return True
        if pinned:
            return row['object_id'] in pinned
        return (not schools or row.get('institution', '').split(' · ')[0] in schools) and matches_conditions(row, research_request)
    def keyword_score(row):
        if not eligible(row):
            return 0
        if row['object_type'] == 'research_opportunity':
            return research_score(row, question, pinned=row['object_id'] in pinned)
        return _keyword_score(row, question, terms)
    # For a broad request such as "学习资源", do not invent topical relevance.
    keyword = {key: score for row in rows if (score := keyword_score(row)) > 0
               for key in [(row['object_type'], row['object_id'])]}
    warnings, semantic = [], {}
    if rows and terms:
        try:
            semantic = semantic_search(rows, question, index=index)
        except (SemanticError, OSError, ValueError) as error:
            warnings.append(str(error) if isinstance(error, SemanticError) else 'semantic_unavailable')
    eligible_keys = {(row['object_type'], row['object_id']) for row in rows if eligible(row)}
    semantic = {key: score for key, score in semantic.items() if key in eligible_keys}
    # Relation counts/freshness must not turn a weak semantic candidate into a recommendation.
    semantic = {key: score for key, score in semantic.items() if score >= 0.45 or key in keyword}
    keyword_order = sorted(keyword, key=lambda key: (-keyword[key], key))
    semantic_order = sorted(semantic, key=lambda key: (-semantic[key], key))
    rrf = {}
    for ranking in (keyword_order, semantic_order):
        for rank, key in enumerate(ranking, start=1):
            rrf[key] = rrf.get(key, 0) + 1 / (60 + rank)
    weights = retrieval_weights()
    if not semantic:
        available = sum(value for key, value in weights.items() if key != 'semantic') or 1
        weights = {key: value / available if key != 'semantic' else 0 for key, value in weights.items()}
    by_key = {(row['object_type'], row['object_id']): row for row in rows}
    result = []
    for key in rrf:
        row = by_key[key].copy()
        if row.get('evidence_blocks'):
            preferred = 'recruitment' if research_request['recruitment'] else 'achievements' if research_request['achievements'] else 'introduction'
            row['evidence_blocks'] = sorted(row['evidence_blocks'], key=lambda block: block['section'] != preferred)
        source_score = 1.0 if row['verified_at'] else 0.55
        row['retrieval_score'] = round(
            weights['keyword'] * keyword.get(key, 0) + weights['semantic'] * min(1, semantic.get(key, 0)) +
            weights['mode'] * _mode_fit(row['object_type'], mode) + weights['source'] * source_score +
            weights['freshness'] * _freshness(row) + weights['relation'] * min(
                1, sum(len(ids) for ids in row['related_object_ids'].values()) / 3) +
            min(0.05, rrf[key]), 4)
        result.append(row)
    result.sort(key=lambda row: (-row['retrieval_score'], row['object_type'], row['object_id']))
    return result, warnings, 'hybrid' if semantic else 'keyword'


def _competition_rows(question, *, limit=8):
    result = search_competitions(question[:500], mode='hybrid', limit=limit)
    cards = {entry['record_id']: entry['competition']['id'] for entry in result['results']}
    rows, evidence_rows = [], []
    baselines = rank_baselines()
    for position, hit in enumerate(result['hits']):
        source = next(iter(hit['evidence']), None)
        if not source:
            continue
        related = []
        competition_id = cards.get(hit['record_id'])
        if competition_id:
            related = list(ResourceCompetition.objects.filter(
                competition_id=competition_id, resource__publication_status='published',
                resource__availability='available').values_list('resource__code', flat=True))
        rows.append(_record('competition', hit['record_id'], hit['title'], hit['summary'],
                            '\n'.join(p['text'] for p in hit['passages']) or hit['summary'], source['url'],
                            source_type='approved_knowledge', verified_at=source.get('verified_at'),
                            version=hit['content_hash'], category=(hit['category'] or {}).get('name', ''),
                            related={'resource': related, 'competition_id': [str(competition_id)] if competition_id else []}))
        baseline = baselines['competition_hybrid'] if result['mode_used'] == 'hybrid' else baselines['competition_keyword']
        exact_bonus = baselines['competition_exact_bonus'] if question.casefold().strip() == hit['title'].casefold() else 0
        rows[-1]['retrieval_score'] = round(min(1.0, baseline + exact_bonus - position * baselines['competition_rank_step']), 4)
        passages = hit['passages'][:2] or [{'text': hit['summary'] or hit['title'],
                                            'evidence_ids': [linked['id'] for linked in hit['evidence']]}]
        for passage in passages:
            for linked in hit['evidence']:
                if linked['id'] in passage['evidence_ids']:
                    evidence_rows.append({
                        'kind': 'knowledge', 'entity_id': hit['record_id'], 'version': hit['content_hash'],
                        'content_hash': hit['content_hash'], 'title': hit['title'], 'edition': hit['edition'],
                        'url': linked['url'], 'text': passage['text'], 'locator': linked.get('locator'),
                        'verified_at': linked.get('verified_at'), 'published_on': None,
                        'status': 'published', 'status_note': hit['edition'] or '赛事资料',
                        'source_type': 'approved_knowledge', 'reviewed': True,
                        'internal_url': None,
                    })
    return rows, evidence_rows, result['mode_used'], result['warnings']


def _related_competitions(ids):
    if not ids:
        return []
    wanted = set(ids)
    result = []
    for source in collect_records(['competition']):
        if source['id'] not in wanted or not source.get('_ai_ready'):
            continue
        result.append(_record('competition', source['id'], source['title'], source['text'][:500],
                              source['text'], source['source_urls'][0], source_type='platform_competition',
                              published_at=source['published_at'], verified_at=source['verified_at'],
                              version=source['version']))
    return result


def retrieve_unified(question, mode, route, *, index=None, group_selector=None, limit=8):
    secondary = public_secondary_records(group_selector=group_selector)
    ranked, warnings, secondary_mode = _rank(secondary, question, mode, index=index)
    include_competition = mode == 'competition' or (mode == 'smart' and 'competition' in route.domains)
    competitions, knowledge_rows, competition_mode = [], [], 'not_requested'
    if include_competition:
        competitions, knowledge_rows, competition_mode, comp_warnings = _competition_rows(question)
        warnings.extend(item['code'] if isinstance(item, dict) else str(item) for item in comp_warnings)
        curated_ids = {f'db-{identifier}' for row in competitions
                       for identifier in row['related_object_ids'].get('competition_id', [])}
        for source in retrieve_platform(question, route):
            if source['kind'] != 'competition' or source['entity_id'] in curated_ids:
                continue
            identifier = source['entity_id']
            related = list(ResourceCompetition.objects.filter(
                competition_id=int(identifier[3:]), resource__publication_status='published',
                resource__availability='available').values_list('resource__code', flat=True)) if identifier.startswith('db-') else []
            row = _record('competition', identifier, source['title'], source['text'][:500],
                          source['text'], source['url'], source_type='platform_competition',
                          published_at=source['published_on'], verified_at=source['verified_at'],
                          version=source['version'], related={'resource': related})
            row['retrieval_score'] = rank_baselines()['direct_competition']
            row['status_note'] = source['status_note']
            competitions.append(row)
    primary = competitions + ranked
    unique = {}
    for row in primary:
        # Multiple imported documents can describe the same titled edition.
        identity = (row['object_type'], re.sub(r'[\W_]+', '', row['title']).casefold())
        if identity not in unique or row['retrieval_score'] > unique[identity]['retrieval_score']:
            unique[identity] = row
    primary = list(unique.values())
    topical_anchors = [term for term in ('数学建模', '人工智能', '机器学习', '数据分析', '机器人', '人机交互') if term in question]
    if topical_anchors:
        primary = [row for row in primary if all(term in ' '.join((row['title'], row['summary'], row['content'], *row['tags'], *row['direction']))
                                                 for term in topical_anchors)]
    if re.search(r'入门|零基础|初学', question):
        technologies = re.findall(r'[a-z][a-z0-9+#.-]{1,}', question.casefold())
        def foundation(row):
            if row['object_type'] != 'resource' or not technologies:
                return False
            title = row['title'].casefold()
            if not all(term in title for term in technologies):
                return False
            for term in technologies:
                title = title.replace(term, '')
            title = re.sub(r'官方|教程|入门|基础|学习|指南|课程|文档|快速|起步|语言|程序设计|编程|初学者|[\W_\d]', '', title)
            return not title
        if any(foundation(row) for row in primary):
            primary = [row for row in primary if row['object_type'] != 'resource' or foundation(row)]
    wants_resources = bool(re.search(r'资源|教程|课程|学习|准备', question))
    if mode == 'research' and not wants_resources:
        primary = [row for row in primary if row['object_type'] in ('research_opportunity', 'research_group')]
    if mode == 'competition' and competitions and not wants_resources:
        primary = [row for row in primary if row['object_type'] == 'competition']
    exact = [row for row in primary if row['title'].casefold() in question.casefold()]
    if exact:
        primary = exact
    elif mode == 'smart':
        allowed = {kind for domain, kinds in (
            ('competition', ('competition',)), ('project', ('research_opportunity', 'research_group')),
            ('resource', ('resource',))) if domain in route.domains for kind in kinds}
        primary = [row for row in primary if row['object_type'] in allowed]
    if mode == 'competition':
        primary.sort(key=lambda row: (row['object_type'] != 'competition', -row['retrieval_score']))
    elif mode == 'research':
        primary.sort(key=lambda row: (row['object_type'] not in ('research_opportunity', 'research_group'), -row['retrieval_score']))
    elif mode == 'resource':
        primary.sort(key=lambda row: (row['object_type'] != 'resource', -row['retrieval_score']))
    else:
        primary.sort(key=lambda row: -row['retrieval_score'])
    if mode == 'smart':
        # Keep one relevant hit per requested domain before filling by score.
        requested = [kind for domain, kinds in (
            ('competition', ('competition',)), ('project', ('research_opportunity', 'research_group')),
            ('resource', ('resource',))) if domain in route.domains for kind in kinds]
        reserved = []
        for kind in requested:
            candidate = next((row for row in primary if row['object_type'] == kind), None)
            if candidate and candidate not in reserved:
                reserved.append(candidate)
        selected = sorted(reserved, key=lambda row: -row['retrieval_score'])[:limit]
        for row in primary:
            if len(selected) >= limit:
                break
            if row not in selected:
                selected.append(row)
        selected.sort(key=lambda row: -row['retrieval_score'])
    else:
        selected = primary[:limit]
    selected_keys = {(row['object_type'], row['object_id']) for row in selected}
    by_key = {(row['object_type'], row['object_id']): row for row in secondary}
    related_competition_ids = {identifier for row in selected if row['object_type'] == 'resource'
                               for identifier in row['related_object_ids'].get('competition', [])}
    by_key.update({(row['object_type'], row['object_id']): row
                   for row in _related_competitions(related_competition_ids)})
    for row in selected[:4]:
        for kind, ids in row['related_object_ids'].items():
            for identifier in ids[:3]:
                key = (kind, identifier)
                related = by_key.get(key)
                if related and key not in selected_keys:
                    added = related.copy()
                    added['retrieval_score'] = round(max(added['retrieval_score'], row['retrieval_score'] * 0.7), 4)
                    added['relation_reason'] = f"与{row['title']}已建立关联"
                    selected.append(added)
                    selected_keys.add(key)
    selected = selected[:limit + 4]
    selected_knowledge_ids = {row['object_id'] for row in selected
                              if row['source_type'] == 'approved_knowledge'}
    knowledge_rows = [row for row in knowledge_rows if row['entity_id'] in selected_knowledge_ids]
    return {'records': selected, 'knowledge_rows': knowledge_rows,
            'knowledge_status': 'ready' if knowledge_rows else 'no_published_knowledge' if include_competition else 'not_requested',
            'mode_used': competition_mode if competitions else secondary_mode, 'warnings': warnings}


def as_evidence(row):
    group_label = ('课题组原文名称：' + row['research_group_label'] + '\n'
                   if row.get('research_group_label') else '')
    internal_url = ('/resources/' + row['object_id'] if row['object_type'] == 'resource' else
                    '/competitions/' + row['object_id'][3:] if row['object_type'] == 'competition'
                    and re.fullmatch(r'db-\d+', row['object_id']) else None)
    return {'kind': row['object_type'], 'entity_id': row['object_id'], 'version': row['version'],
            'title': row['title'], 'url': row['source_url'],
            'internal_url': internal_url,
            'text': (group_label + row['summary'] + '\n' + row['content'])[:1800],
            'verified_at': row['verified_at'], 'published_on': row['published_at'],
            'status': row['status'], 'status_note': row.get('relation_reason') or row.get('status_note') or row['category'],
            'source_type': row['source_type'], 'reviewed': bool(row['verified_at']),
            'object_type': row['object_type'], 'retrieval_score': row['retrieval_score']}


def recommendations(rows):
    resources = {row['object_id']: row for row in rows if row['object_type'] == 'resource'}
    visible = {(row['object_type'], row['object_id']) for row in rows}
    return [{'object_type': row['object_type'], 'object_id': row['object_id'],
             'title': row['title'], 'reason': row.get('relation_reason') or row['summary'][:140],
             'related_object_ids': {kind: [identifier for identifier in ids if (kind, identifier) in visible]
                                    for kind, ids in row['related_object_ids'].items() if isinstance(ids, list) and kind in
                                    ('competition', 'resource', 'research_opportunity', 'research_group')},
             'source_url': row['source_url'],
             'facts': row.get('facts', {}), 'field_links': row.get('field_links', {}),
             'research_group_label': row.get('research_group_label') or '',
             'reviewed': bool(row['verified_at']), 'retrieval_score': row['retrieval_score'],
             'status': row['status'], 'content_status': row.get('content_status') or '',
             'status_note': row.get('status_note') or '',
             'related_resources': [{'title': resources[code]['title'], 'source_url': resources[code]['source_url']}
                                   for code in row['related_object_ids'].get('resource', []) if code in resources][:3]}
            for row in rows[:6]]


def evidence_rows(rows, question=None):
    """Round-robin labs first, then additional independently sourced sections."""
    pools = []
    for row in rows:
        if row['source_type'] == 'approved_knowledge':
            continue
        base = as_evidence(row)
        blocks = row.get('evidence_blocks')
        if blocks and question:
            if re.search(r'招募|招收|申请|报名|加入|资格|本科生.*可以|时间投入|工作内容|参与工作', question):
                preferred = [block for block in blocks if block['section'] == 'recruitment']
                blocks = preferred or [block for block in blocks if block['section'] == 'introduction']
            else:
                blocks = [block for block in blocks if block['section'] != 'recruitment']
        pools.append([{**base, 'title': row['title'] + ' · ' + {'introduction': '研究介绍',
                       'achievements': '研究成果', 'recruitment': '招募信息'}[block['section']],
                       'text': block['text'], 'url': block['url'], 'verified_at': block['verified_at'],
                       'published_on': block['published_on'], 'fields': block['fields'],
                       'section': block['section']} for block in blocks] if blocks else [base])
    return [pool[i] for i in range(max((len(pool) for pool in pools), default=0)) for pool in pools if i < len(pool)]
