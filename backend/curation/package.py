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


def load_package(filename, batches=()):
    filename = Path(filename).resolve()
    require(filename.stat().st_size <= 30_000_000, '资料包 JSON 超过 30 MB。')
    data = json.loads(filename.read_text(encoding='utf-8-sig'))
    require(data.get('schema_version') == 1, '不支持的 schema_version。')
    require(isinstance(data.get('package_id'), str) and re.fullmatch(r'[a-z0-9-]{1,100}', data['package_id']), '资料包编号无效。')
    require(isinstance(data.get('catalog'), list), '缺少 catalog 清单。')
    codes = [x['code'] for x in data['catalog']]
    require(len(codes) == len(set(codes)), '目录编号重复。')
    for row in data['catalog']:
        require(re.fullmatch(r'2026(?:1[3-9][0-9]|2[0-5][0-9])', row['code']) is not None
                and 2026131 <= int(row['code']) <= 2026255, '目录超出 131—255 范围。')
        require(row.get('name') and row.get('grade') and row.get('departments'), '目录信息不完整。')
    selected = {c for c in codes if not batches or (int(c[-3:]) - 131) // 25 + 1 in batches}
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
    for kind in ('resources', 'documents'):
        for row in data.get(kind, []):
            require(set(row.get('competition_codes', [])) <= identities['competitions'], f'{row["code"]} 引用了不存在的赛事。')
            if kind == 'documents':
                require(set(row.get('resource_codes', [])) <= identities['resources'], f'{row["code"]} 引用了不存在的资源。')
    result['_root'] = str(filename.parent)
    result['_hash'] = digest(data)
    result['_batches'] = sorted(set(batches))
    return result
