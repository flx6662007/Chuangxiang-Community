"""Read-only resource regression against the configured DB; no chat/API calls."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / 'docs/resource-evaluation/cases.json'
IMPLEMENTATION_FILES = (
    'backend/ai_services/chat.py', 'backend/ai_services/unified.py',
    'backend/ai_services/fusion.py', 'backend/ai_services/router.py',
    'backend/ai_services/resource_retrieval.py',
)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def context_payload(prepared):
    """Inspect the actual final provider context, not intermediate ranked rows."""
    for message in prepared.get('provider_messages', []):
        text = message.get('content', '')
        start = text.find('{')
        if start < 0:
            continue
        try:
            value = json.loads(text[start:])
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict) and 'PLATFORM_CONTEXT' in value:
            return value
    return {}


def recommendation_precision_failures(case, cards):
    """Human relevance judgments, including wrong materials of the same type."""
    failures = []
    forbidden = set(case.get('forbidden_recommendation_resource_ids', []))
    for card in cards:
        if card.get('object_type') == 'resource' and card.get('object_id') in forbidden:
            failures.append('off_topic_resource:' + card['object_id'])
        for pattern in case.get('forbidden_recommendation_title_patterns', []):
            if re.search(pattern, card.get('title', ''), re.I):
                failures.append('off_topic_recommendation:' + card['title'])
        if (case.get('allowed_recommendation_kinds')
                and card.get('object_type') not in case['allowed_recommendation_kinds']):
            named_competition = card.get('object_type') == 'competition' and any(
                re.search(pattern, card.get('title', ''), re.I)
                for pattern in case.get('allowed_competition_title_patterns', []))
            if not named_competition:
                failures.append('out_of_scope_recommendation:' + card.get('title', ''))
    return sorted(set(failures))


def check_case(case, prepared, resources, catalog_competitions):
    sources, cards = prepared.get('sources', []), prepared.get('recommendations', [])
    resource_sources = [s for s in sources if s.get('object_type') == 'resource' or s.get('kind') == 'resource']
    resource_cards = [c for c in cards if c.get('object_type') == 'resource']
    source_ids = {s.get('entity_id') for s in resource_sources}
    card_ids = {c.get('object_id') for c in resource_cards}
    expected = set(case['expected_resource_ids'])
    failures = []
    source_hit, card_hit = bool(expected & source_ids), bool(expected & card_ids)
    if expected and not source_hit:
        failures.append('target_missing_from_final_sources')
    if expected and not card_hit:
        failures.append('target_missing_from_final_recommendations')
    # Real public identity and title are gold-side checks, independent of ranking.
    for field, rows in (('entity_id', resource_sources), ('object_id', resource_cards)):
        for row in rows:
            identifier = row.get(field)
            if identifier not in resources:
                failures.append('unknown_or_nonpublic_resource:' + str(identifier))
            elif row.get('title') != resources[identifier]['title']:
                failures.append('resource_title_mismatch:' + str(identifier))
    for card in resource_cards:
        if card.get('object_id') not in source_ids:
            failures.append('card_without_final_resource_source:' + str(card.get('object_id')))
        if not (card.get('internal_url') or card.get('source_url')):
            failures.append('resource_card_without_entry:' + str(card.get('object_id')))
    precision_failures = recommendation_precision_failures(case, cards)
    failures.extend(precision_failures)
    for pattern in case.get('absent_identity_patterns', []):
        # Do not reject legitimate alternatives merely because the question had no exact hit.
        for row in [*sources, *cards]:
            if re.search(pattern, row.get('title', ''), re.I):
                failures.append('absent_identity_presented_as_result:' + row['title'])
    if case.get('require_no_recommendations') and cards:
        failures.append('unexpected_recommendation_for_specific_absent_course')
    if case.get('require_no_sources') and sources:
        failures.append('unrelated_sources_for_specific_absent_course')
    relation_check = None
    if case.get('required_catalog_context'):
        code = case['required_catalog_context']
        competition_ids = catalog_competitions.get(code, set())
        payload = context_payload(prepared)
        slots = [row for key in ('PLATFORM_CONTEXT', 'KNOWLEDGE_CONTEXT')
                 for row in payload.get(key, [])]
        target_context = [row for row in slots if row.get('entity_id') in expected]
        # A raw db-ID alone does not tell the model it means 蓝桥杯. Require both
        # the true FK relation and a visible name in this final context.
        relation_present = any(competition_ids.intersection(
            row.get('related_object_ids', {}).get('competition', [])) for row in target_context)
        visible_name = any(case['required_catalog_name'] in (
            row.get('title', '') + ' ' + row.get('excerpt', '')) for row in slots)
        relation_check = {'catalog_code': code, 'competition_ids': sorted(competition_ids),
                          'target_context_present': bool(target_context),
                          'relation_present': relation_present, 'catalog_name_visible': visible_name}
        if not (target_context and relation_present and visible_name):
            failures.append('catalog_relation_not_explainable_in_final_context')
    return {
        'id': case['id'], 'split': case['split'], 'question': case['question'],
        'mode': prepared.get('mode'), 'expected_resource_ids': sorted(expected),
        'target_in_sources': source_hit if expected else None,
        'target_in_recommendations': card_hit if expected else None,
        'other_recommendation_titles': [c.get('title') for c in cards if c.get('object_id') not in expected],
        'precision_failures': precision_failures,
        'precision_judgment': case.get('precision_judgment'),
        'passed': not failures, 'failures': sorted(set(failures)),
        'sources': [{'kind': s.get('object_type') or s.get('kind'), 'id': s.get('entity_id'),
                     'title': s.get('title'), 'url': s.get('url')} for s in sources],
        'recommendations': [{'kind': c.get('object_type'), 'id': c.get('object_id'),
                             'title': c.get('title'), 'internal_url': c.get('internal_url'),
                             'source_url': c.get('source_url')} for c in cards],
        'catalog_context': relation_check, 'early_content': prepared.get('early_content'),
        'route': prepared.get('route'), 'retrieval': prepared.get('retrieval'),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument('--mode', action='append', choices=('smart', 'resource'),
                        help='Repeat to evaluate both modes; default: smart.')
    parser.add_argument('--split', choices=('all', 'observed', 'generalization'), default='all')
    parser.add_argument('--case', action='append', dest='case_ids', help='Run selected exact case IDs.')
    parser.add_argument('--keyword-only', action='store_true',
                        help='Temporarily disable local semantic indices for a keyword comparison.')
    parser.add_argument('--require-semantic', action='store_true',
                        help='Require a configured unified index and no retrieval fallback warnings.')
    args = parser.parse_args()
    if args.keyword_only and args.require_semantic:
        parser.error('--keyword-only and --require-semantic cannot be combined.')
    fixture = read_json(args.fixture)
    cases = [case for case in fixture['cases']
             if (args.split == 'all' or case['split'] == args.split)
             and (not args.case_ids or case['id'] in args.case_ids)]
    if not cases:
        parser.error('No cases selected.')
    if args.case_ids and set(args.case_ids) - {case['id'] for case in cases}:
        parser.error('Unknown or filtered --case ID.')
    # No model key is needed. Existing DB credentials remain private in Django's
    # normal environment; local BGE may run, but never downloads its weights.
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    sys.path.insert(0, str(ROOT / 'backend'))
    code_hashes = {path: digest(ROOT / path) for path in IMPLEMENTATION_FILES if (ROOT / path).exists()}
    import django
    django.setup()
    from django.db import connection, transaction
    from ai_services.chat import _prepare_chat
    from ai_services.client import OpenAICompatibleClient
    from competition_catalog.models import CatalogBinding
    from resources.models import Resource

    prohibited_calls = []

    def prohibit(*unused_args, **unused_kwargs):
        prohibited_calls.append('A model, HTTP, or web-search call was attempted.')
        raise AssertionError(prohibited_calls[-1])

    results, fixture_errors = [], []
    modes = list(dict.fromkeys(args.mode or ['smart']))
    started = time.monotonic()
    if connection.vendor != 'postgresql':
        raise SystemExit('Use the configured PostgreSQL DB; this evaluator opens a READ ONLY transaction.')
    with ExitStack() as stack:
        for method in ('complete_json', 'complete_text', 'stream_text'):
            stack.enter_context(patch.object(OpenAICompatibleClient, method, side_effect=prohibit))
        for target in ('ai_services.chat.search_external', 'httpx.Client.send',
                       'httpx.AsyncClient.send', 'urllib.request.urlopen'):
            stack.enter_context(patch(target, side_effect=prohibit))
        try:
            import requests.sessions
        except ImportError:
            pass
        else:
            stack.enter_context(patch.object(requests.sessions.Session, 'request', side_effect=prohibit))
        if args.keyword_only:
            stack.enter_context(patch.dict(os.environ, {
                'UNIFIED_SEMANTIC_INDEX': '', 'COMPETITION_SEMANTIC_INDEX': ''}))
        stack.enter_context(transaction.atomic())
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        records = list(Resource.objects.filter(publication_status='published', availability='available')
                       .exclude(code__startswith='demo-').exclude(title__contains='【虚构样例】')
                       .values('code', 'title', 'description', 'access_url').order_by('code'))
        resources = {r['code']: r for r in records}
        catalog_competitions = {}
        for code, competition_id in CatalogBinding.objects.filter(
                competition__publication_status='published').values_list('entry__code', 'competition_id'):
            catalog_competitions.setdefault(code, set()).add(f'db-{competition_id}')
        for case in cases:
            for identifier in case['expected_resource_ids']:
                if identifier not in resources:
                    fixture_errors.append(case['id'] + ': expected public resource missing: ' + identifier)
            for pattern in case.get('absent_identity_patterns', []):
                present = [r['code'] for r in records if re.search(
                    pattern, json.dumps(r, ensure_ascii=False), re.I)]
                if present:
                    fixture_errors.append(case['id'] + ': negative identity is now in DB: ' + ', '.join(present))
        if not fixture_errors:
            for mode in modes:
                for case in cases:
                    before = time.monotonic()
                    try:
                        prepared = _prepare_chat([{'role': 'user', 'content': case['question']}],
                                                 mode, object(), details=True, web_search=False)
                        result = check_case(case, prepared, resources, catalog_competitions)
                    except Exception as error:
                        # Never write exception text: a DB/transport error can contain private configuration.
                        result = {'id': case['id'], 'split': case['split'], 'mode': mode,
                                  'expected_resource_ids': case['expected_resource_ids'], 'passed': False,
                                  'failures': ['execution_error:' + type(error).__name__]}
                    result['seconds'] = round(time.monotonic() - before, 3)
                    results.append(result)
                    print(json.dumps({key: result[key] for key in ('id', 'mode', 'passed', 'failures')},
                                     ensure_ascii=False), flush=True)
        transaction.set_rollback(True)
    positive = [r for r in results if r['expected_resource_ids']]
    negative = [r for r in results if not r['expected_resource_ids']]
    final_hashes = {path: digest(ROOT / path) for path in IMPLEMENTATION_FILES if (ROOT / path).exists()}
    code_changed = final_hashes != code_hashes
    semantic_warnings = [{'id': r['id'], 'mode': r['mode'], 'warnings': r['retrieval']['warnings']}
                         for r in results if r.get('retrieval', {}).get('warnings')]
    semantic_requirement_passed = (bool(os.getenv('UNIFIED_SEMANTIC_INDEX')) and not semantic_warnings
                                   and any(r.get('retrieval', {}).get('mode_used') == 'hybrid' for r in results))
    summary = {'runs': len(results), 'passed': sum(r['passed'] for r in results),
               'failed': sum(not r['passed'] for r in results), 'positive_runs': len(positive),
               'precision_failed_runs': sum(bool(r.get('precision_failures')) for r in results),
               'targets_in_sources_and_cards': sum(r.get('target_in_sources') is True
                                                   and r.get('target_in_recommendations') is True for r in positive),
               'negative_runs': len(negative), 'negative_passed': sum(r['passed'] for r in negative),
               'prohibited_calls': len(prohibited_calls), 'fixture_errors': fixture_errors,
               'implementation_changed_during_run': code_changed,
               'retrieval_warnings': semantic_warnings,
               'semantic_requirement_passed': semantic_requirement_passed if args.require_semantic else None,
               'groups': [{'mode': mode, 'split': split, 'runs': len(group),
                           'passed': sum(r['passed'] for r in group),
                           'target_hits': sum(r.get('target_in_sources') is True
                                              and r.get('target_in_recommendations') is True for r in group)}
                          for mode in modes for split in ('observed', 'generalization')
                          if (group := [r for r in results if r['mode'] == mode and r['split'] == split])]}
    report = {'created_at': datetime.now(timezone.utc).isoformat(),
              'evaluation': 'resource_prepare_chat_no_generation',
              'retrieval_configuration': 'forced_keyword' if args.keyword_only else 'current_local_configuration',
              'modes': modes, 'public_resource_count': len(records),
              'public_resource_fingerprint': hashlib.sha256(json.dumps(records, ensure_ascii=False,
                    sort_keys=True).encode()).hexdigest(), 'fixture_sha256': digest(args.fixture),
              'code_sha256': code_hashes, 'code_sha256_at_end': final_hashes,
              'limits': ['No generated answer was evaluated; negative checks cover only returned identities.',
                         'A passed link check proves presence in the response, not HTTP availability.',
                         'Current configured local semantic search may fall back; inspect retrieval.warnings.'],
              'seconds': round(time.monotonic() - started, 3), 'summary': summary, 'results': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 2 if fixture_errors else 1 if (summary['failed'] or prohibited_calls or code_changed
                                         or args.require_semantic and not semantic_requirement_passed) else 0


if __name__ == '__main__':
    raise SystemExit(main())
