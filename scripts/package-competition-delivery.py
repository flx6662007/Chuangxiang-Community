"""Build three versioned handoff ZIPs and verify their contents and SHA-256."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = Path('docs/competition-knowledge')
MAINTENANCE = Path('docs/competition-knowledge-maintenance')
EXCLUDED_MAINTENANCE = {'git-status.txt', 'git-diff-stat.txt'}
CODE = [
    'backend/curation/__init__.py', 'backend/curation/product.py',
    'backend/curation/test_product.py', 'backend/curation/test_knowledge_delivery.py',
    'backend/information_library/__init__.py', 'backend/information_library/competition_search.py',
    'backend/information_library/semantic.py', 'backend/information_library/test_competition_search.py',
    'backend/requirements-retrieval.txt',
    'scripts/audit-competition-sources.py', 'scripts/build-competition-knowledge.py',
    'scripts/build-knowledge-imports.py', 'scripts/check-competition-knowledge.py',
    'scripts/check-knowledge-rebuild.py', 'scripts/competition-search.py',
    'scripts/prepare-competition-model.py', 'scripts/build-competition-evaluation.py',
    'scripts/evaluate-competition-search.py', 'scripts/test-competition-evaluation.py',
    'scripts/build-curated-package.py', 'scripts/build-research-package.py',
    'scripts/package-competition-delivery.py',
    'docs/competition-research/tongji-2026-001-089/build_package.py',
    'docs/competition-search-handoff.md', 'docs/competition-delivery.md',
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def files_under(relative):
    return sorted(path for path in (ROOT / relative).rglob('*')
                  if path.is_file() and '__pycache__' not in path.parts)


def verify_archive(path, entry):
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f'Invalid ZIP CRC: {path.name}')
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError(f'Duplicate archive member: {path.name}')
        if set(archive.namelist()) != {row['path'] for row in entry['files']}:
            raise ValueError(f'Unexpected archive members: {path.name}')
        for row in entry['files']:
            name = Path(row['path'])
            if name.is_absolute() or '..' in name.parts:
                raise ValueError(f'Unsafe archive path: {row["path"]}')
            data = archive.read(row['path'])
            if len(data) != row['bytes'] or digest(data) != row['sha256']:
                raise ValueError(f'Archive content mismatch: {row["path"]}')
    if digest(path.read_bytes()) != entry['sha256']:
        raise ValueError(f'Archive SHA-256 mismatch: {path.name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'deliverables/competition-knowledge-v1')
    parser.add_argument('--verify', action='store_true', help='Verify an existing delivery manifest and all ZIP members')
    args = parser.parse_args()
    if args.verify:
        manifest = json.loads((args.output / 'manifest.json').read_text(encoding='utf-8'))
        for entry in manifest['archives']:
            verify_archive(args.output / entry['file'], entry)
        print(json.dumps({'ok': True, 'corpus_version': manifest['corpus_version'],
                          'archives': len(manifest['archives'])}))
        return
    version = json.loads((ROOT / PUBLIC / 'version.json').read_text(encoding='utf-8'))['version']
    groups = {
        'competition-materials': [(p, p.relative_to(ROOT / PUBLIC).as_posix()) for p in files_under(PUBLIC)],
        'competition-integration': [(p, p.relative_to(ROOT).as_posix()) for p in
                                   [*(ROOT / p for p in CODE), *files_under(PUBLIC),
                                    *files_under(Path('docs/competition-evaluation'))]],
        'competition-maintenance': [(p, p.relative_to(ROOT).as_posix()) for p in files_under(MAINTENANCE)
                                   if p.name not in EXCLUDED_MAINTENANCE],
    }
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {'schema_version': 1, 'corpus_version': version, 'archives': []}
    for name, files in groups.items():
        path = args.output / f'{name}-v1-{version}.zip'
        entry = {'file': path.name, 'files': []}
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for source, archive_name in sorted(files, key=lambda pair: pair[1]):
                data = source.read_bytes()
                info = zipfile.ZipInfo(archive_name, date_time=(2026, 10, 4, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
                entry['files'].append({'path': archive_name, 'bytes': len(data), 'sha256': digest(data)})
        entry['bytes'] = path.stat().st_size
        entry['sha256'] = digest(path.read_bytes())
        verify_archive(path, entry)
        manifest['archives'].append(entry)
    (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'ok': True, 'corpus_version': version, 'archives': [
        {'file': r['file'], 'files': len(r['files']), 'bytes': r['bytes']} for r in manifest['archives']]}))


if __name__ == '__main__':
    main()
