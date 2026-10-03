"""可脱离数据库校验的人工资料包格式。只读取显式文件，不访问网络。"""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


class PackageError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def require(condition, message):
    if not condition:
        raise PackageError(message)


def public_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return parsed.scheme in ('http', 'https') and bool(parsed.hostname) and not parsed.username and not parsed.password


COMPETITION_FIELDS = {
    'title', 'edition', 'summary', 'description', 'level', 'organizer', 'tracks', 'eligibility',
    'participation_type', 'team_size_min', 'team_size_max', 'registration_method', 'registration_url',
    'campus_arrangements', 'registration_deadline', 'submission_deadline', 'campus_deadline', 'deadline_notes',
    'registration_deadline_at', 'registration_deadline_timezone',
    'submission_deadline_at', 'submission_deadline_timezone', 'campus_deadline_at', 'campus_deadline_timezone',
}
RESOURCE_FIELDS = {'title', 'description', 'provider', 'access_url', 'source_note', 'availability'}


def package_scope(data):
    """各交付范围显式选择；旧包默认131—255，不允许参数扩张范围。"""
    if 'catalog_scope' not in data:
        return {'first': 131, 'last': 255, 'batch_size': 25}
    scope = data['catalog_scope']
    if isinstance(scope, dict) and set(scope) == {'start', 'end', 'batch_size'}:
        require(all(type(scope[key]) is int for key in scope)
                and scope == {'start': 90, 'end': 130, 'batch_size': 25},
                '90—130资料包范围声明无效。')
        return {'first': 90, 'last': 130, 'batch_size': 25}
    allowed = {'first': 1, 'last': 89, 'batch_size': 25}
    require(isinstance(scope, dict) and scope.keys() == allowed.keys()
            and all(type(scope[key]) is int and scope[key] == value
                    for key, value in allowed.items()),
            'catalog_scope 仅接受1—89或90—130的明确交付范围；131—255旧包请省略此字段。')
    return scope


def load_package(filename, batches=()):
    filename = Path(filename).resolve()
    require(filename.stat().st_size <= 30_000_000, '资料包 JSON 超过 30 MB。')
    data = json.loads(filename.read_text(encoding='utf-8-sig'))
    require(data.get('schema_version') == 1, '不支持的 schema_version。')
    require(isinstance(data.get('package_id'), str) and re.fullmatch(r'[a-z0-9-]{1,100}', data['package_id']), '资料包编号无效。')
    scope = package_scope(data)
    first, last, batch_size = (scope[key] for key in ('first', 'last', 'batch_size'))
    batch_numbers = list(range(1, (last - first) // batch_size + 2))
    require(isinstance(batches, (list, tuple)) and all(
        type(batch) is int and batch in batch_numbers for batch in batches),
        f'批次必须为 1—{batch_numbers[-1]} 范围内的整数。')
    require(isinstance(data.get('catalog'), list), '缺少 catalog 清单。')
    codes = [x['code'] for x in data['catalog']]
    require(len(codes) == len(set(codes)), '目录编号重复。')
    for row in data['catalog']:
        require(isinstance(row['code'], str) and re.fullmatch(r'2026[0-9]{3}', row['code']) is not None
                and first <= int(row['code'][-3:]) <= last, f'目录超出 {first}—{last} 范围。')
        require(row.get('name') and row.get('grade') and row.get('departments'), '目录信息不完整。')
    selected = {c for c in codes if not batches or (int(c[-3:]) - first) // batch_size + 1 in batches}
    require(bool(selected), '所选批次没有目录条目。')
    result = {**data, 'catalog': [x for x in data['catalog'] if x['code'] in selected]}
    identities = {}
    for kind in ('competitions', 'resources', 'documents'):
        rows = data.get(kind, [])
        require(isinstance(rows, list), f'{kind} 必须为数组。')
        ids = [x.get('code') for x in rows]
        require(all(isinstance(c, str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', c) and len(c) <= 80 for c in ids), f'{kind} 编码无效。')
        require(len(ids) == len(set(ids)), f'{kind} 编码重复。')
        identities[kind] = set(ids)
        result[kind] = []
        for row in rows:
            links = row.get('catalog_codes', [])
            require(isinstance(links, list) and links and set(links) <= set(codes), f'{row["code"]} 目录关联无效。')
            require(len(links) == len(set(links)), f'{row["code"]} 目录关联重复。')
            if set(links) & selected:
                # 跨批次共用资源保留稳定的完整载荷；导入时仅链接已存在对象。
                result[kind].append(row)
            if kind != 'documents':
                fields = row.get('fields', {})
                allowed = COMPETITION_FIELDS if kind == 'competitions' else RESOURCE_FIELDS
                require(isinstance(fields, dict) and not (set(fields) - allowed), f'{row["code"]} 包含不允许写入的字段。')
                require(bool(fields.get('title')), f'{row["code"]} 缺少标题。')
                if kind == 'competitions':
                    require(bool(fields.get('edition')), f'{row["code"]} 必须有实际届次。')
                    require(row.get('sources'), f'{row["code"]} 必须有来源。')
                    require(sum(s.get('is_primary', False) for s in row['sources']) == 1, f'{row["code"]} 必须有一个主来源。')
                    for source in row['sources']:
                        require(set(source) <= {'source_type', 'source_name', 'source_url', 'is_primary', 'source_published_on'}, '来源含未知字段。')
                        require(isinstance(source.get('source_name'), str) and source['source_name'].strip(), f'{row["code"]} 来源名称不能为空。')
                        require(source.get('source_type') in ('official', 'campus') and public_url(source.get('source_url', '')), '赛事来源无效。')
                else:
                    require(public_url(fields.get('access_url', '')), f'{row["code"]} 资源链接无效。')
            else:
                require(bool(row.get('title')) and bool(row.get('body')), f'{row["code"]} 缺少知识正文。')
                require(row.get('sources') and all(public_url(s.get('url', '')) for s in row['sources']), f'{row["code"]} 缺少可追溯来源。')
                for attachment in row.get('attachments', []):
                    rel = Path(attachment['path'])
                    require(not rel.is_absolute() and '..' not in rel.parts, '附件路径必须位于资料包目录内。')
                    target = (filename.parent / rel).resolve()
                    require(target.is_relative_to(filename.parent), '附件路径越界。')
                    require(target.is_file(), f'附件不存在：{rel}')
                    require(hashlib.sha256(target.read_bytes()).hexdigest() == attachment.get('sha256'), f'附件哈希不符：{rel}')
    references = data.get('references', {})
    require(isinstance(references, dict) and set(references) <= {'competitions', 'resources'}, '复用清单无效。')
    result['references'] = {}
    for kind in ('competitions', 'resources'):
        rows = references.get(kind, [])
        require(isinstance(rows, list), '复用清单必须为数组。')
        seen = set()
        result['references'][kind] = []
        for row in rows:
            require(set(row) == {'code', 'package_id', 'payload_hash', 'catalog_codes'}, '复用声明字段无效。')
            code = row['code']
            require(isinstance(code, str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', code)
                    and len(code) <= 80 and code not in identities[kind] and code not in seen, '复用编码重复或无效。')
            require(isinstance(row['package_id'], str) and re.fullmatch(r'[a-z0-9-]{1,100}', row['package_id'])
                    and row['package_id'] != data['package_id'], '复用来源包无效。')
            require(isinstance(row['payload_hash'], str) and re.fullmatch(r'[a-f0-9]{64}', row['payload_hash']), '复用载荷哈希无效。')
            links = row['catalog_codes']
            require(isinstance(links, list) and links and len(links) == len(set(links))
                    and set(links) <= set(codes), '复用目录关联无效。')
            seen.add(code)
            if set(links) & selected:
                result['references'][kind].append(row)
        identities[kind].update(seen)
    for kind in ('resources', 'documents'):
        for row in data.get(kind, []):
            require(set(row.get('competition_codes', [])) <= identities['competitions'], f'{row["code"]} 引用了不存在的赛事。')
            if kind == 'documents':
                require(set(row.get('resource_codes', [])) <= identities['resources'], f'{row["code"]} 引用了不存在的资源。')
    result['_root'] = str(filename.parent)
    result['_hash'] = digest(data)
    result['_batches'] = sorted(set(batches))
    result['_batch_numbers'] = batch_numbers
    result['_catalog_scope'] = scope
    return result
