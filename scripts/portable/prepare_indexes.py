"""Build the shipped AI indexes against a fresh, isolated demonstration DB."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess

from launcher import build_child_env, CREATE_DEMO_USERS, external_python_dll_directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-root', type=Path, required=True)
    parser.add_argument('--build-data', type=Path, required=True,
                        help='New empty private directory for the temporary build database.')
    args = parser.parse_args()
    root, data = args.package_root.resolve(), args.build_data.resolve()
    if data.exists() and any(data.iterdir()):
        raise SystemExit('Use a new empty --build-data directory; no existing DB is modified.')
    if data == root or data.is_relative_to(root / 'app/frontend'):
        raise SystemExit('Build DB cannot be placed in a served directory.')
    data.mkdir(parents=True, exist_ok=True)
    env = build_child_env(root, data, 'index-build', 18765, secrets.token_urlsafe(48), secrets.token_urlsafe(32), {})
    (root / 'index').mkdir(exist_ok=True)
    commands = [
        ['migrate', '--noinput'],
        ['shell', '--command', CREATE_DEMO_USERS],
        ['loaddata', str(root / 'data/public-fixture.json')],
        ['rebuild_ai_index', '--output', str(root / 'index/competitions.npz')],
        ['rebuild_unified_index', '--output', str(root / 'index/unified.npz')],
    ]
    for command in commands:
        print('Preparing:', command[0], flush=True)
        with (data / 'index-build.log').open('a', encoding='utf-8') as log:
            with external_python_dll_directory():
                result = subprocess.run([str(root / 'runtime/python.exe'), str(root / 'app/backend/manage.py'), *command],
                    cwd=root / 'app/backend', env=env, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode:
            raise SystemExit(f'{command[0]} failed; inspect the private index-build.log.')
    print('Both portable indexes are ready.', flush=True)


if __name__ == '__main__':
    main()
