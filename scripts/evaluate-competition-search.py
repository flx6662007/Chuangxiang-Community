"""Evaluate fixed competition-search judgments; model errors are never passes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def file_hash(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def runtime_versions():
    result = {}
    for package in ('numpy', 'torch', 'sentence-transformers'):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = None
    return result


def load_fixture(directory, split, corpus):
    manifest = read_json(directory / 'manifest.json')
    if manifest['corpus_version'] != corpus['version']:
        raise ValueError('corpus_version_mismatch: use the corpus frozen with these judgments')
    path = directory / f'{split}.jsonl'
    digest = file_hash(path)
    if digest != manifest['files'][path.name]['sha256']:
        raise ValueError('fixture_hash_mismatch: frozen questions were edited')
    cases = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(cases) != manifest['files'][path.name]['count']:
        raise ValueError('fixture_count_mismatch')
    return cases


def _values(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def hard_violations(record, filters, as_of):
    """Independent gold-side check. Never call the production match/filter helper."""
    fields = record.get('fields', {})
    evidence = record.get('field_evidence', {})
    source_ids = {source['id'] for source in record.get('sources', [])
                  if source.get('url', '').startswith(('http://', 'https://'))
                  and source.get('locator') and source.get('verified_at')}
    violations = []
    catalog_codes = set(record.get('catalog_codes') or [record.get('catalog_code')])

    def reject(key):
        if key not in violations:
            violations.append(key)

    def evidenced(key):
        return bool(source_ids.intersection(evidence.get(key, [])))

    for key, expected in filters.items():
        if key == 'catalog_codes':
            if not catalog_codes.intersection(expected):
                reject(key)
        elif key == 'code':
            if expected not in catalog_codes and expected != record.get('code'):
                reject(key)
        elif key == 'edition':
            if expected != record.get('edition'):
                reject(key)
        elif key in ('category', 'level'):
            if record.get(key) != expected:
                reject(key)
        elif key == 'participation_type':
            actual = fields.get(key)
            if not evidenced(key) or not (actual == expected or (actual == 'both' and expected in ('team', 'individual'))):
                reject(key)
        elif key == 'team_size':
            lower, upper = fields.get('team_size_min'), fields.get('team_size_max')
            # A missing bound is an information gap, not proof of eligibility.
            if lower is None or upper is None or not evidenced('team_size_min') or not evidenced('team_size_max'):
                reject(key)
            elif not lower <= expected <= upper:
                reject(key)
        elif key in ('education', 'grade', 'major'):
            field_name = {'grade': 'grades', 'major': 'majors'}.get(key, key)
            if expected not in _values(fields.get(field_name)) or not evidenced(field_name):
                reject(key)
        elif key == 'registration_status':
            start, end = fields.get('registration_start'), fields.get('registration_deadline')
            dated_status = None
            if end and end < as_of:
                dated_status = 'closed'
            elif start and as_of < start:
                dated_status = 'upcoming'
            elif start and end and start <= as_of <= end:
                dated_status = 'open'
            official_today = (fields.get('registration_status') == expected
                              and fields.get('status_as_of') == as_of
                              and evidenced('registration_status') and evidenced('status_as_of')
                              and dated_status in (None, expected))
            if expected == 'open':
                if not official_today and (not start or not end or not evidenced('registration_start') or not evidenced('registration_deadline') or not start <= as_of <= end):
                    reject(key)
            elif expected == 'closed':
                if not official_today and (not end or not evidenced('registration_deadline') or not end < as_of):
                    reject(key)
            elif expected == 'upcoming':
                if not official_today and (not start or not evidenced('registration_start') or not as_of < start):
                    reject(key)
        elif key in ('deadline_from', 'deadline_to'):
            deadline = fields.get('registration_deadline')
            if not deadline or not evidenced('registration_deadline'):
                reject(key)
            elif (key == 'deadline_from' and deadline < expected) or (key == 'deadline_to' and deadline > expected):
                reject(key)
        else:
            raise ValueError(f'Gold evaluator does not support filter {key!r}')
    return violations


def evaluate_case(case, response, corpus):
    records = {r['id']: r for r in corpus['records']}
    hits = response.get('hits', [])[:5]
    hit_ids = [h['record_id'] for h in hits]
    relevant = set(case['relevant_ids'])
    details = {'id': case['id'], 'group': case['group'], 'scenario': case['scenario'],
               'expect_empty': case['expect_empty'], 'returned_ids': hit_ids,
               'hit_at_5': bool(relevant.intersection(hit_ids)) if relevant else None,
               'empty_correct': not hits if case['expect_empty'] else None,
               'hard_violations': [], 'reason_count': 0, 'grounded_reason_count': 0,
               'gold_evidence_hit': False, 'unresolved_evidence_ids': [],
               'hits_without_reason': sum(not hit.get('match_reasons') for hit in hits)}
    if case['expect_empty'] and not hits:
        explanation = response.get('empty_result')
        conditions = explanation.get('conditions', []) if isinstance(explanation, dict) else []
        details['empty_explanation'] = explanation
        details['empty_explanation_valid'] = bool(
            isinstance(explanation, dict)
            and explanation.get('code') in ('no_condition_match', 'no_topic_match', 'empty_corpus')
            and isinstance(explanation.get('message'), str) and explanation['message'].strip()
            and all(any(item.get('field') == key and item.get('value') == value for item in conditions)
                    for key, value in case['filters'].items()))
    for hit in hits:
        record = records.get(hit['record_id'])
        if record is None:
            details['hard_violations'].append({'record_id': hit['record_id'], 'filters': ['unknown_record']})
            continue
        violations = hard_violations(record, case['filters'], case['as_of'])
        if record.get('review_status') != 'approved' or record.get('publication_status') != 'published':
            violations.append('visibility')
        if violations:
            details['hard_violations'].append({'record_id': record['id'], 'filters': violations})
        source_ids = {s['id'] for s in record.get('sources', [])
                      if s.get('url') and s.get('locator') and s.get('verified_at')}
        returned_evidence = {s['id'] for s in hit.get('evidence', [])}
        details['unresolved_evidence_ids'].extend(sorted(returned_evidence - source_ids))
        if record['id'] in relevant and returned_evidence.intersection(case['evidence_ids']):
            details['gold_evidence_hit'] = True
        for reason in hit.get('match_reasons', []):
            details['reason_count'] += 1
            ids = set(reason.get('evidence_ids', []))
            if ids and ids <= source_ids and ids <= returned_evidence:
                details['grounded_reason_count'] += 1
    return details


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * fraction) - 1))]


def summarize(details):
    positives = [d for d in details if not d['expect_empty']]
    negatives = [d for d in details if d['expect_empty']]
    semantic = [d for d in positives if d['scenario'] == 'semantic']
    latencies = [d['latency_ms'] for d in details if 'latency_ms' in d]
    errors = [d for d in details if d.get('error')]
    reason_count = sum(d.get('reason_count', 0) for d in details)
    grounded = sum(d.get('grounded_reason_count', 0) for d in details)
    correct_empties = [d for d in negatives if d.get('empty_correct')]
    ratio = lambda items, key: sum(bool(d.get(key)) for d in items) / len(items) if items else None
    metrics = {'cases': len(details), 'positive_cases': len(positives), 'empty_cases': len(negatives),
               'operational_errors': len(errors), 'hit_at_5': ratio(positives, 'hit_at_5'),
               'empty_accuracy': ratio(negatives, 'empty_correct'),
               'semantic_hit_at_5': ratio(semantic, 'hit_at_5'),
               'gold_evidence_hit_rate': ratio(positives, 'gold_evidence_hit'),
               'hard_violation_count': sum(len(d.get('hard_violations', [])) for d in details),
               'reason_count': reason_count, 'grounded_reason_count': grounded,
               'hits_without_reason': sum(d.get('hits_without_reason', 0) for d in details),
               'empty_explanation_coverage': ratio(correct_empties, 'empty_explanation_valid'),
               'evidence_reference_coverage': grounded / reason_count if reason_count else None,
               'unresolved_evidence_count': sum(len(d.get('unresolved_evidence_ids', [])) for d in details),
               'latency_ms': {'median': statistics.median(latencies) if latencies else None,
                              'p95': percentile(latencies, .95), 'max': max(latencies) if latencies else None}}
    metrics['passes_targets'] = bool(not errors and (metrics['hit_at_5'] is None or metrics['hit_at_5'] >= .9)
                                    and metrics['hard_violation_count'] == 0
                                    and metrics['empty_accuracy'] in (None, 1)
                                    and metrics['unresolved_evidence_count'] == 0
                                    and metrics['hits_without_reason'] == 0
                                    and metrics['empty_explanation_coverage'] in (None, 1)
                                    and grounded == reason_count)
    return metrics


def run_mode(cases, corpus, search, mode, index=None):
    details = []
    for case in cases:
        start = time.perf_counter()
        try:
            response = search(case['query'], filters=case['filters'], preferences=case['preferences'],
                              as_of=case['as_of'], mode=mode, limit=5, corpus=corpus, index=index)
            if not isinstance(response, dict) or not isinstance(response.get('hits'), list):
                raise RuntimeError('invalid_search_response')
            # Hybrid degradation remains useful to callers but is not a
            # successfully evaluated semantic/hybrid mode.
            warnings = response.get('warnings', [])
            if warnings:
                raise RuntimeError('search_warnings: ' + json.dumps(warnings, ensure_ascii=False))
            if response.get('mode_used', mode) != mode:
                raise RuntimeError('search_mode_degraded')
            detail = evaluate_case(case, response, corpus)
        except Exception as error:
            detail = {'id': case['id'], 'group': case['group'], 'scenario': case['scenario'],
                      'expect_empty': case['expect_empty'], 'error': type(error).__name__ + ': ' + str(error),
                      'hit_at_5': False if not case['expect_empty'] else None,
                      'empty_correct': False if case['expect_empty'] else None}
        detail['latency_ms'] = round((time.perf_counter() - start) * 1000, 3)
        details.append(detail)
    return {'metrics': summarize(details), 'cases': details}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=ROOT / 'docs/competition-knowledge/corpus.json')
    parser.add_argument('--fixtures', type=Path, default=ROOT / 'docs/competition-evaluation')
    parser.add_argument('--split', choices=('dev', 'test'), default='dev')
    parser.add_argument('--probes', type=Path, help='Additional independent development cases; incompatible with --split test')
    parser.add_argument('--modes', nargs='+', choices=('keyword', 'semantic', 'hybrid'), default=['keyword', 'semantic', 'hybrid'])
    parser.add_argument('--index', type=Path)
    parser.add_argument('--semantic-threshold', type=float, help='Development calibration only; final test uses the chosen value')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.probes and args.split == 'test':
        parser.error('--probes is for development diagnostics only')
    if args.semantic_threshold is not None:
        if not -1 <= args.semantic_threshold <= 1:
            parser.error('--semantic-threshold must be between -1 and 1')
        os.environ['COMPETITION_SEMANTIC_THRESHOLD'] = str(args.semantic_threshold)
    corpus = read_json(args.corpus)
    cases = read_json(args.probes)['cases'] if args.probes else load_fixture(args.fixtures, args.split, corpus)
    if args.probes:
        text = json.dumps(corpus, ensure_ascii=False)
        for case in cases:
            if case.get('split') != 'dev':
                raise ValueError('Diagnostic cases must belong to development')
            found = [term for term in case.get('absence_terms', []) if term in text]
            if found:
                raise ValueError(f"Probe needs relevance review after corpus expansion: {case['id']}: {found}")
    from information_library.competition_search import search_competitions
    from information_library.semantic import DEFAULT_THRESHOLD
    index = None
    if args.index:
        from information_library.semantic import load_index
        index = load_index(args.index)
    report = {'schema_version': 1, 'split': 'dev-probes' if args.probes else args.split, 'corpus_version': corpus['version'],
              'run_started_at': datetime.now(timezone.utc).isoformat(),
              'parameters': {'limit': 5, 'semantic_threshold': float(os.getenv('COMPETITION_SEMANTIC_THRESHOLD', DEFAULT_THRESHOLD))},
              'fixture_sha256': file_hash(args.probes or args.fixtures / f'{args.split}.jsonl'),
              'evaluator_sha256': file_hash(Path(__file__)),
              'implementation_sha256': {name: file_hash(ROOT / 'backend/information_library' / name)
                                        for name in ('competition_search.py', 'semantic.py')},
              'environment': {'python': platform.python_version(), 'system': platform.system(),
                              'machine': platform.machine(), 'processor': platform.processor(),
                              'packages': runtime_versions()},
              'index': index.metadata if index is not None else None,
              'evidence_metric_note': 'Coverage validates source references. Whether a cited passage entails every reason still requires evidence review.',
              'modes': {mode: run_mode(cases, corpus, search_competitions, mode, index) for mode in args.modes}}
    # Do not duplicate potentially large chunk data in each evaluation report.
    if report['index']:
        report['index'] = {k: v for k, v in report['index'].items() if k not in ('chunks', 'record_hashes', 'record_fingerprints')}
    if 'keyword' in report['modes'] and 'hybrid' in report['modes']:
        keyword, hybrid = (report['modes'][name]['metrics'] for name in ('keyword', 'hybrid'))
        comparable = not keyword['operational_errors'] and not hybrid['operational_errors']
        if keyword['positive_cases']:
            report['comparison'] = {
                'comparable': comparable,
                'hybrid_hit_at_5_gain': hybrid['hit_at_5'] - keyword['hit_at_5'] if comparable else None,
                'semantic_subset_gain': hybrid['semantic_hit_at_5'] - keyword['semantic_hit_at_5'] if comparable and hybrid['semantic_hit_at_5'] is not None and keyword['semantic_hit_at_5'] is not None else None,
                'hybrid_not_worse': hybrid['hit_at_5'] >= keyword['hit_at_5'] if comparable else None,
            }
        else:
            report['comparison'] = {'comparable': comparable,
                                    'hybrid_not_worse': hybrid['empty_accuracy'] >= keyword['empty_accuracy'] if comparable else None}
    acceptance_mode = 'hybrid' if 'hybrid' in report['modes'] else args.modes[-1]
    report['acceptance'] = {
        'mode': acceptance_mode,
        'passes': report['modes'][acceptance_mode]['metrics']['passes_targets']
                  and report.get('comparison', {}).get('hybrid_not_worse', True) is True,
        'baseline_policy': 'Keyword and semantic-only scores are reported as comparisons; the hybrid target governs a three-mode run.',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'split': report['split'], 'modes': {k: v['metrics'] for k, v in report['modes'].items()},
                      'comparison': report.get('comparison')}, ensure_ascii=False, indent=2))
    if any(m['metrics']['operational_errors'] for m in report['modes'].values()):
        return 2
    return 0 if report['acceptance']['passes'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
