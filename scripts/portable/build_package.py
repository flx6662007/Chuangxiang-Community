"""Build a Windows review folder from an installed runtime and public fixture.

Never copies .env, working databases or user accounts. API credentials are
configured by the owner in review.env after building, not embedded in code.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def copy_tree(source, target, *, ignored=()):
    shutil.copytree(source, target, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo', *ignored))


def runtime_info(python):
    output = subprocess.check_output([str(python), '-c',
        'import json,sys; from pathlib import Path; '
        'print(json.dumps({"base":sys.base_prefix,"site":str(Path(sys.prefix)/"Lib/site-packages"),'
        '"version":sys.version,"tag":f"{sys.version_info.major}{sys.version_info.minor}"}))'], text=True)
    return json.loads(output)


def prepare_runtime(python, target):
    info = runtime_info(python)
    base, site = Path(info['base']), Path(info['site'])
    target.mkdir(parents=True, exist_ok=True)
    marker = target / '.runtime-build-info.json'
    signature = {**info, 'source_site': str(site.resolve())}
    if marker.exists() and json.loads(marker.read_text(encoding='utf-8')) == signature:
        return info
    for pattern in ('python*.exe', '*.dll', 'LICENSE*'):
        for source in base.glob(pattern):
            shutil.copy2(source, target / source.name)
    copy_tree(base / 'DLLs', target / 'DLLs')
    copy_tree(base / 'Lib', target / 'Lib', ignored=('site-packages', 'test', 'tests', 'idlelib', 'ensurepip'))
    copy_tree(site, target / 'Lib/site-packages', ignored=('pip', 'pip-*.dist-info'))
    # An isolated search path avoids registry/PYTHONPATH dependencies on the
    # author's machine. Backend app imports remain explicit and relocatable.
    (target / f"python{info['tag']}._pth").write_text(
        'Lib\nDLLs\nLib/site-packages\n../app/backend\nimport site\n', encoding='utf-8')
    marker.write_text(json.dumps(signature), encoding='utf-8')
    return info


def tracked_backend(target):
    files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard',
                                     '-z', '--', 'backend'], cwd=ROOT).decode('utf-8').split('\0')
    for relative in files:
        if not relative:
            continue
        source = ROOT / relative
        if not source.is_file() or source.name.startswith('.env') or source.suffix in ('.pyc', '.sqlite3'):
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def build(args):
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=True)
    if not (target / '.portable-build').exists() and any(target.iterdir()):
        raise SystemExit('Output must be empty or contain this builder marker.')
    (target / '.portable-build').write_text('Chuangxiang portable review package\n', encoding='utf-8')
    info = prepare_runtime(args.python.resolve(), target / 'runtime')
    if args.runtime_only:
        print(json.dumps({'runtime_ready': True, 'python': info['version']}, ensure_ascii=False))
        return
    if not args.fixture or not args.fixture.is_file():
        raise SystemExit('--fixture must be an exported public fixture.')
    if not (ROOT / 'frontend/dist/index.html').is_file():
        raise SystemExit('Build frontend first: npm run build.')
    if not args.launcher or not args.launcher.is_file():
        raise SystemExit('--launcher must be the built launcher EXE.')
    license_source = ROOT / 'scripts/portable/licenses'
    for name in ('PyInstaller-COPYING.txt', 'FlagEmbedding-LICENSE'):
        if not (license_source / name).is_file():
            raise SystemExit(f'Missing required distribution license: {name}')
    tracked_backend(target / 'app')
    copy_tree(ROOT / 'frontend/dist', target / 'app/frontend')
    copy_tree(license_source, target / 'licenses')
    (target / 'data').mkdir(exist_ok=True)
    shutil.copy2(args.fixture, target / 'data/public-fixture.json')
    shutil.copy2(args.launcher, target / '启动创享.exe')
    if args.model:
        copy_tree(args.model, target / 'models/bge-small-zh-v1.5', ignored=('.cache', '.git'))
    for name, path in [('unified.npz', args.resource_index), ('competitions.npz', args.competition_index)]:
        if path:
            (target / 'index').mkdir(exist_ok=True)
            shutil.copy2(path, target / 'index' / name)
    (target / 'portable-manifest.json').write_text(json.dumps({
        'package_id': args.package_id, 'version': '2026-10-10',
        'platform': 'Windows x64', 'python': info['version'],
        'data': 'public records plus isolated demonstration accounts',
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree_changes_included': True,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Do not copy the developer's environment or produce a key-bearing archive.
    (target / 'review.env.example').write_text(
        '# Owner configures review.env once before privately delivering the package.\n'
        'DEEPSEEK_API_KEY=\nDEEPSEEK_BASE_URL=https://api.deepseek.com\n'
        'DEEPSEEK_MODEL=deepseek-flash\n', encoding='utf-8')
    (target / '使用说明.txt').write_text(
        '创享社区 · Windows 评审演示版\n\n'
        '1. 将整个压缩包解压到一个文件夹，勿在压缩包内直接运行。\n'
        '2. 双击“启动创享.exe”，首次启动将自动准备演示数据。\n'
        '3. 网页会自动打开；登录账号可在启动器中查看。\n'
        '4. 保持启动器运行，结束体验时在启动器中停止并退出。\n\n'
        '无需安装 Python、Node.js 或 PostgreSQL，无需管理员权限。\n'
        '这是本机独立演示数据，组队与反馈操作不会影响线上社区。\n'
        '赛事与资料在本地检索；AI 回答、访问官方链接需要网络。\n'
        '包制作者须先配置评审专用模型密钥；未配置时资料页面仍可使用。\n'
        '密钥不包含在公开压缩包中，也不可上传 GitHub。\n', encoding='utf-8-sig')
    print(json.dumps({'package_ready': str(target), 'contains_api_key': False}, ensure_ascii=False))
    if args.zip:
        create_public_zip(target, args.zip)


def create_public_zip(folder, destination):
    folder, destination = folder.resolve(), destination.resolve()
    if destination.is_relative_to(folder):
        raise SystemExit('ZIP destination must be outside the package folder.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(folder.rglob('*')):
            relative = path.relative_to(folder)
            if (not path.is_file() or path.name in ('review.env', '.portable-build', '.runtime-build-info.json')
                    or path.name == '.env' or path.name.startswith('.env.')
                    or '__pycache__' in relative.parts or 'user-data' in relative.parts
                    or path.suffix in ('.pyc', '.log', '.sqlite3', '.pid')):
                continue
            archive.write(path, Path(folder.name) / relative)
    print(json.dumps({'archive': str(destination), 'bytes': destination.stat().st_size}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime-only', action='store_true')
    parser.add_argument('--fixture', type=Path)
    parser.add_argument('--launcher', type=Path)
    parser.add_argument('--model', type=Path)
    parser.add_argument('--resource-index', type=Path)
    parser.add_argument('--competition-index', type=Path)
    parser.add_argument('--package-id', default='chuangxiang-review-20261010')
    parser.add_argument('--zip', type=Path)
    build(parser.parse_args())
