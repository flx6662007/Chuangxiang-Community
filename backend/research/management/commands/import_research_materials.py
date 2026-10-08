"""Preview and merge independently curated research cards by stable ID."""
import json
import os
import re
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from common.public_content import safe_source_url
from information_library import selectors

FIELDS = {'id', 'title', 'unit', 'summary', 'participation', 'evidenceNote', 'date', 'verifiedOn', 'sourceUrl'}


def validate_rows(rows, *, incoming=False):
    if not isinstance(rows, list) or len(rows) > 1000 or (incoming and not rows):
        raise ValueError('条目数须为 1—1000（目标文件允许为空）')
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or not FIELDS <= set(row):
            raise ValueError('每条须包含约定的九个字段')
        if incoming and set(row) != FIELDS:
            raise ValueError('导入条目须恰好包含九个文本字段')
        if any(not isinstance(row[k], str) or len(row[k]) > 20000 for k in FIELDS):
            raise ValueError('字段须为文本，且不超过 20000 字符')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', row['id']) or row['id'] in ids:
            raise ValueError('编号无效或重复')
        if not row['title'].strip() or not safe_source_url(row['sourceUrl']):
            raise ValueError('标题或来源无效')
        for field in ('date', 'verifiedOn'):
            if row[field]:
                date.fromisoformat(row[field])
        ids.add(row['id'])


class Command(BaseCommand):
    help = '按稳定编号合并科研资料；默认预演，导入不开放科研展示。'

    def add_arguments(self, parser):
        parser.add_argument('--source', type=Path, required=True)
        parser.add_argument('--target', type=Path, help='独立候选文件；缺省为站点 editorial.json')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--database', action='store_true', help='导入科研数据库模型，而非内容文件')
        parser.add_argument('--publish', action='store_true', help='数据库导入时发布新建或草稿记录；不恢复下架记录')

    def handle(self, *args, **options):
        temporary = None
        try:
            data = json.loads(options['source'].read_text(encoding='utf-8-sig'))
            rows = data['laboratories']
            validate_rows(rows, incoming=True)
            profiles = data.get('profiles')
            if profiles is not None:
                from research.presentation import validate_card_details
                if not isinstance(profiles, dict) or set(profiles) != {r['id'] for r in rows}:
                    raise ValueError('profiles 必须与导入编号一一对应')
                for profile in profiles.values():
                    validate_card_details(profile)
            if options.get('database'):
                if options.get('target'):
                    raise ValueError('--database 不能与 --target 同时使用')
                if data.get('scope') == 'national' and any(not r['id'].startswith('research-cn-') for r in rows):
                    raise ValueError('全国包条目必须使用 research-cn- 编号')
                from research.importer import import_cards
                report = import_cards(rows, apply=options['apply'], publish=options.get('publish', False), profiles=profiles, sources=data.get('sources'))
                self.stdout.write(json.dumps(report, ensure_ascii=False))
                return
            if options.get('publish'):
                raise ValueError('--publish 仅可与 --database 同时使用')
            target = options.get('target') or selectors.EDITORIAL_PATH
            current = json.loads(target.read_text(encoding='utf-8-sig')) if target.exists() else {'laboratories': []}
            if not isinstance(current, dict):
                raise ValueError('目标文件须为 JSON 对象')
            existing = current.get('laboratories', [])
            validate_rows(existing)
            by_id = {row['id']: row for row in existing}
            incoming = {row['id']: row for row in rows}
            # Preserve editorial metadata, including review/publication controls.
            merged = [{**row, **incoming.get(row['id'], {})} for row in existing]
            merged.extend(row for row in rows if row['id'] not in by_id)
            conflicts = []
            urls = {}
            for row in merged:
                url = row['sourceUrl'].rstrip('/')
                if url in urls:
                    conflicts.append({'reason': '同一来源对应不同编号，请先核对实体', 'ids': [urls[url], row['id']]})
                urls[url] = row['id']
            if len(merged) > 1000:
                conflicts.append({'reason': '合并后超过 1000 条'})
            if (data.get('scope') == 'national' or current.get('scope') == 'national') and any(not r['id'].startswith('research-cn-') for r in merged):
                conflicts.append({'reason': '全国包不能混入其他范围记录；请用 --target 指向独立全国候选文件'})
            report = {
                'count': len(rows), 'total': len(merged),
                'added': sum(r['id'] not in by_id for r in rows),
                'updated': sum(r['id'] in by_id and (any(by_id[r['id']][k] != r[k] for k in FIELDS) or (profiles is not None and current.get('profiles', {}).get(r['id']) != profiles[r['id']])) for r in rows),
                'retained': sum(r['id'] not in incoming for r in existing),
                'conflicts': conflicts, 'applied': False,
                'unchanged': merged == existing and (profiles is None or all(current.get('profiles', {}).get(k) == v for k, v in profiles.items())), 'target': str(target),
            }
            if options['apply'] and conflicts:
                raise ValueError(json.dumps(report, ensure_ascii=False))
            if options['apply'] and not report['unchanged']:
                current['laboratories'] = merged
                if profiles is not None:
                    current['profiles'] = {**current.get('profiles', {}), **profiles}
                if data.get('scope') == 'national':
                    current['scope'] = 'national'
                target.parent.mkdir(parents=True, exist_ok=True)
                with NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent, delete=False) as temp:
                    temporary = temp.name
                    json.dump(current, temp, ensure_ascii=False, indent=2)
                    temp.write('\n')
                os.replace(temporary, target)
                temporary = None
            report['applied'] = bool(options['apply'])
        except (ValueError, KeyError, TypeError, OSError, AttributeError, ValidationError) as exc:
            raise CommandError(str(exc)) from None
        finally:
            if temporary:
                Path(temporary).unlink(missing_ok=True)
        self.stdout.write(json.dumps(report, ensure_ascii=False))
