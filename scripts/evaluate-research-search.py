"""Read-only evaluation of the published research corpus; never calls a chat model."""
import argparse
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from ai_services.unified import public_secondary_records, _rank, _keyword_score, evidence_rows
from ai_services.router import query_terms
from ai_services.research_retrieval import intent, matches_conditions
from ai_services.unified_index import search, load_index
from ai_services.fusion import fuse
from information_library.semantic import LocalBGEEncoder, SemanticError
from research.models import ResearchOpportunity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--keyword-only', action='store_true')
    args = parser.parse_args()
    questions = json.loads((ROOT / 'docs/research-national/ai-retrieval-evaluation.json').read_text(encoding='utf8'))['questions']
    rows = public_secondary_records()
    objects = {f'db-{obj.pk}': obj for obj in ResearchOpportunity.objects.filter(publication_status='published')}
    codes = {key: obj.code for key, obj in objects.items()}
    if not args.keyword_only:
        path = Path(os.environ['UNIFIED_SEMANTIC_INDEX'])
        index = load_index(str(path), path.stat().st_mtime_ns, path.stat().st_size)
        encoder = LocalBGEEncoder()
    results = []
    for case in questions:
        query = case['question']
        # Reproduce the former keyword-only text fields for a transparent baseline.
        baseline = []
        for row in rows:
            obj = objects.get(row['object_id'])
            if not obj:
                continue
            content = '\n'.join(filter(None, [obj.summary, obj.description, obj.recruiting_entity, obj.institution,
                                             obj.work_content, obj.eligibility, obj.requirements, obj.duration_text]))
            score = _keyword_score({**row, 'summary': content[:500], 'content': content}, query, query_terms(query))
            if score > 0:
                baseline.append((score, row['object_id']))
        baseline.sort(key=lambda pair: (-pair[0], pair[1]))
        with patch('ai_services.unified.semantic_search', side_effect=SemanticError('unified_index_unconfigured')):
            keyword, _, _ = _rank(rows, query, 'research')
        if args.keyword_only:
            hybrid, mode = keyword, 'keyword'
        else:
            with patch('ai_services.unified.semantic_search', side_effect=lambda records, question, **kw:
                       search(records, question, index=index, encoder=encoder)):
                hybrid, _, mode = _rank(rows, query, 'research')
        sources, _ = fuse(evidence_rows(hybrid[:5]), [], [])
        expected = case.get('expected')
        entry = {'question': query, 'expected': expected,
                 'old_keyword_top5': [codes.get(key, key) for _, key in baseline[:5]],
                 'keyword_top5': [codes.get(r['object_id'], r['object_id']) for r in keyword[:5]],
                 'hybrid_top5': [codes.get(r['object_id'], r['object_id']) for r in hybrid[:5]],
                 'mode': mode, 'sources': [{'title': s['title'], 'url': s['url'], 'fields': s['fields']} for s in sources],
                 'conditions_pass': all(matches_conditions(r, intent(query)) for r in hybrid) if case.get('conditions') else None,
                 'duplicate_count': len(hybrid) - len({(r['object_type'], r['object_id']) for r in hybrid})}
        results.append(entry)
    topical = [r for r in results if r['expected']]
    report = {'records': len(rows), 'questions': len(results), 'topic_questions': len(topical),
              'old_keyword_hit_at_5': sum(r['expected'] in r['old_keyword_top5'] for r in topical),
              'keyword_hit_at_5': sum(r['expected'] in r['keyword_top5'] for r in topical),
              'hybrid_hit_at_5': sum(r['expected'] in r['hybrid_top5'] for r in topical),
              'condition_cases_passed': sum(r['conditions_pass'] is True for r in results),
              'duplicate_count': sum(r['duplicate_count'] for r in results), 'results': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}))
    if (report['keyword_hit_at_5'] != len(topical) or report['hybrid_hit_at_5'] != len(topical)
            or report['condition_cases_passed'] != len(results) - len(topical) or report['duplicate_count']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
