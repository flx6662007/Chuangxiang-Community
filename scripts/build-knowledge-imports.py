"""Build knowledge packages using the existing curation import format.

Linked overlays reference existing editions. Standalone packages need no parent
packages. Both create draft knowledge documents without publishing business objects.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from curation.package import digest, load_package


def build(corpus, mapping, originals, catalog_entries=(), catalog_source_url='', *, standalone=False):
    # Previously deferred entries are absent from the old import manifests.
    # Reuse their existing directory identity without exposing this metadata in
    # the public corpus or inventing a new business Competition object.
    catalogs = {row['code']: {**{key: row[key] for key in ('code', 'name', 'grade', 'levels', 'departments')},
                             'source_url': row.get('source_url') or catalog_source_url}
                for row in catalog_entries}
    competitions = {}
    for package in originals:
        catalogs.update({r['code']: r for r in package['catalog']})
        for row in package.get('competitions', []):
            competitions[row['code']] = (package['package_id'], row)
    origins = {row['record_id']: row for row in mapping}
    products = []
    for first, last in [(1, 89), (90, 130), (131, 255)]:
        selected = [r for r in corpus['records'] if first <= int(r['catalog_code'][-3:]) <= last]
        codes = {c for row in selected for c in row.get('catalog_codes', [row['catalog_code']])
                 if first <= int(c[-3:]) <= last}
        if codes - catalogs.keys():
            raise ValueError(f'Missing catalog metadata: {sorted(codes - catalogs.keys())}')
        references, documents = {}, []
        for record in selected:
            origin = origins.get(record['id'], {})
            competition_code = None if standalone else origin.get('competition_code')
            links = sorted(set(record.get('catalog_codes', [record['catalog_code']])) & codes)
            competition_codes = []
            if competition_code:
                if competition_code not in competitions:
                    raise ValueError(f'Missing edition dependency: {competition_code}')
                package_id, original = competitions[competition_code]
                reference = references.setdefault(competition_code, {
                    'code': competition_code, 'package_id': package_id,
                    'payload_hash': digest(original), 'catalog_codes': [],
                })
                reference['catalog_codes'] = sorted(set(reference['catalog_codes']) | set(links))
                competition_codes.append(competition_code)
            body = '\n\n'.join(f"## {s['heading']}\n\n{s['text']}" for s in record['sections'])
            documents.append({
                # Keep the same document identity in both import modes. Different
                # package owners make the existing importer reject mixing modes,
                # so one search_record cannot become two published documents.
                'code': 'final-' + record['id'], 'title': record['title'],
                'edition': record.get('edition', ''), 'body': body,
                'sources': record['sources'], 'attachments': [],
                'catalog_codes': links, 'competition_codes': competition_codes,
                'resource_codes': [],
                'metadata': {'search_record': record, 'corpus_version': corpus['version'],
                             'content_standard': 'competition-knowledge-v1'},
            })
        package = {
            'schema_version': 1,
            'package_id': f'competition-knowledge-{"standalone-" if standalone else ""}v1-{first:03}-{last:03}',
            'review': {'status': 'pending'}, 'catalog': [catalogs[c] for c in sorted(codes)],
            'competitions': [], 'resources': [], 'documents': documents,
            'references': {'competitions': list(references.values()), 'resources': []},
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
    parser.add_argument('--mapping', type=Path, default=ROOT / 'docs/competition-knowledge-maintenance/product-mapping.json')
    parser.add_argument('--original', type=Path, action='append')
    parser.add_argument('--standalone', action='store_true',
                        help='Build knowledge-only packages without parent edition dependencies; choose one import mode per database')
    parser.add_argument('--catalog', type=Path, default=ROOT / 'backend/competition_catalog/data/tongji-2026.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.standalone and not args.original:
        parser.error('linked mode requires at least one --original package')
    if args.standalone and args.original:
        parser.error('--standalone does not accept --original packages')
    if args.output is None:
        folder = 'standalone-imports' if args.standalone else 'imports'
        args.output = ROOT / 'docs/competition-knowledge-maintenance' / folder
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    catalog = read(args.catalog)
    products = build(read(args.corpus), [] if args.standalone else read(args.mapping),
                     [read(p) for p in args.original or []], catalog['entries'],
                     catalog['source_url'], standalone=args.standalone)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, package in products:
        target = args.output / name
        target.write_text(json.dumps(package, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        loaded = load_package(target)
        print(json.dumps({'file': name, 'documents': len(loaded['documents']),
                          'edition_dependencies': len(loaded['references']['competitions']),
                          'mode': 'standalone' if args.standalone else 'linked'}))


if __name__ == '__main__':
    main()
