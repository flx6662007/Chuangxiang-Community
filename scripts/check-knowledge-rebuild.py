"""Rebuild from delivered inputs and compare every public artifact byte for byte."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', type=Path, default=ROOT / 'docs/competition-knowledge')
    parser.add_argument('--maintenance', type=Path, default=ROOT / 'docs/competition-knowledge-maintenance')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    public, maintenance = args.public.resolve(), args.maintenance.resolve()
    version = json.loads((public / 'version.json').read_text(encoding='utf-8'))
    local = ROOT / '.local'
    local.mkdir(exist_ok=True)
    # Keep the small rebuilt package available for inspecting any mismatch.
    work = Path(tempfile.mkdtemp(prefix='knowledge-rebuild-', dir=local))
    rebuilt, evidence = work / 'public', work / 'maintenance'
    evidence.mkdir()
    inputs = ('verified-supplements.json', 'rechecked-supplements.json',
              'recheck-review.json', 'public-text-revisions.json')
    for name in inputs:
        shutil.copyfile(maintenance / name, evidence / name)
    command = [sys.executable, str(ROOT / 'scripts/build-competition-knowledge.py'),
               '--output', str(rebuilt), '--maintenance', str(evidence),
               '--supplements', str(evidence / 'verified-supplements.json'),
               '--as-of', version['as_of']]
    for number, batch in enumerate(('001-089', '090-130', '131-255'), start=1):
        command += [f'--package-{number}', str(maintenance / 'source-snapshots' / batch)]
    subprocess.run(command, check=True)
    originals = {path.relative_to(public): path for path in public.rglob('*') if path.is_file()}
    copies = {path.relative_to(rebuilt): path for path in rebuilt.rglob('*') if path.is_file()}
    rows = []
    for name in sorted(originals.keys() | copies.keys()):
        original = originals[name].read_bytes() if name in originals else None
        copy = copies[name].read_bytes() if name in copies else None
        rows.append({'file': name.as_posix(), 'identical': original == copy,
                     'sha256': hashlib.sha256(original).hexdigest() if original is not None else None})
    report = {'ok': all(row['identical'] for row in rows), 'corpus_version': version['version'],
              'inputs': list(inputs), 'files': rows}
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
