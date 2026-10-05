"""Build the three knowledge import packages from the final corpus."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from curation.package import load_package


def build(corpus, catalog_entries, catalog_source_url=''):
    catalogs = {row['code']: {**{key: row[key] for key in ('code', 'name', 'grade', 'levels', 'departments')},
                             'source_url': row.get('source_url') or catalog_source_url}
                for row in catalog_entries}
    products = []
    for first, last in [(1, 89), (90, 130), (131, 255)]:
        selected = [r for r in corpus['records'] if first <= int(r['catalog_code'][-3:]) <= last]
        codes = {c for row in selected for c in row.get('catalog_codes', [row['catalog_code']])
                 if first <= int(c[-3:]) <= last}
        if codes - catalogs.keys():
            raise ValueError(f'Missing catalog metadata: {sorted(codes - catalogs.keys())}')
        documents = []
        for record in selected:
            links = sorted(set(record.get('catalog_codes', [record['catalog_code']])) & codes)
            body = '\n\n'.join(f"## {s['heading']}\n\n{s['text']}" for s in record['sections'])
            documents.append({
                'code': 'final-' + record['id'], 'title': record['title'],
                'edition': record.get('edition', ''), 'body': body,
                'sources': record['sources'], 'attachments': [],
                'catalog_codes': links, 'competition_codes': [],
                'resource_codes': [],
                'metadata': {'search_record': record, 'corpus_version': corpus['version'],
                             'content_standard': 'competition-knowledge-v1'},
            })
        package = {
            'schema_version': 1,
            'package_id': f'competition-knowledge-standalone-v1-{first:03}-{last:03}',
            'review': {'status': 'pending'}, 'catalog': [catalogs[c] for c in sorted(codes)],
            'competitions': [], 'resources': [], 'documents': documents,
            'references': {'competitions': [], 'resources': []},
            'corpus_version': corpus['version'],
        }
        if first == 1:
            package['catalog_scope'] = {'first': 1, 'last': 89, 'batch_size': 25}
        elif first == 90:
            package['catalog_scope'] = {'start': 90, 'end': 130, 'batch_size': 25}
        products.append((f'import-{first:03}-{last:03}.json', package))
    return products


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=ROOT / 'docs/competition-knowledge/corpus.json')
    parser.add_argument('--catalog', type=Path, default=ROOT / 'backend/competition_catalog/data/tongji-2026.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/competition-knowledge-maintenance/imports')
    args = parser.parse_args()
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    catalog = read(args.catalog)
    products = build(read(args.corpus), catalog['entries'], catalog['source_url'])
    args.output.mkdir(parents=True, exist_ok=True)
    for name, package in products:
        target = args.output / name
        target.write_text(json.dumps(package, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        loaded = load_package(target)
        print(json.dumps({'file': name, 'documents': len(loaded['documents']),
                          'edition_dependencies': len(loaded['references']['competitions'])}))


if __name__ == '__main__':
    main()
