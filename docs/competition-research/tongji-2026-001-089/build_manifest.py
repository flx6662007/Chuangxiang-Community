"""生成本资料目录的文件校验清单；不纳入运行缓存和清单自身。"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
files = []
for path in sorted(ROOT.rglob('*')):
    if not path.is_file() or '__pycache__' in path.parts or path.name == '文件清单.json':
        continue
    data = path.read_bytes()
    normalization = 'binary' if path.suffix == '.xlsx' else 'CRLF-to-LF'
    if normalization == 'CRLF-to-LF':
        data = data.replace(b'\r\n', b'\n')
    files.append({'path': path.relative_to(ROOT).as_posix(), 'bytes': len(data),
                  'sha256': hashlib.sha256(data).hexdigest(), 'hash_normalization': normalization})
(ROOT / '文件清单.json').write_text(json.dumps({
    'package_id': 'tongji-2026-001-089-20261003',
    'note': '不含清单自身、Python缓存及数据库。文本先将CRLF统一为LF再计算大小和SHA-256；XLSX按原始字节计算。',
    'files': files,
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'{len(files)} files recorded')
