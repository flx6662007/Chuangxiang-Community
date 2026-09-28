"""版本化学校目录与已核实官网；网页不能自行改变采集白名单。"""
from functools import lru_cache
import json
from pathlib import Path

from django.db import transaction

from .models import CatalogBinding, CatalogEntry, OfficialSite

ADAPTER_CATALOG = {'aicomp': '2026020', 'ncda': '2026068'}


@lru_cache(maxsize=1)
def directory():
    return json.loads((Path(__file__).parent / 'data/tongji-2026.json').read_text(encoding='utf-8'))


@transaction.atomic
def initialize_catalog():
    data = directory()
    count = 0
    for row in data['entries']:
        entry_values = {
            'version': data['version'], 'name': row['name'], 'grade': row['grade'], 'levels': row['levels'],
            'departments': row['departments'], 'aliases': row.get('aliases', []), 'source_url': data['source_url'],
        }
        entry, created = CatalogEntry.objects.get_or_create(code=row['code'], defaults=entry_values)
        count += int(created)
        if not created:
            changed = []
            for key, value in entry_values.items():
                if getattr(entry, key) != value:
                    setattr(entry, key, value)
                    changed.append(key)
            # 版本化目录可纠正元信息，但不得恢复人工停用的条目。
            if changed:
                entry.save(update_fields=changed)
        approved_urls = []
        for item in row.get('sites', []):
            if item.get('status') != 'verified':
                continue
            approved_urls.append(item['url'])
            values = {
                'evidence_url': item['evidence_url'], 'kind': item.get('kind', 'competition'),
                'dedicated': item.get('dedicated', False), 'allowed_hosts': item['allowed_hosts'],
                'note': item.get('note', ''),
            }
            site, site_created = OfficialSite.objects.get_or_create(entry=entry, url=item['url'], defaults={
                **values, 'enabled': item.get('enabled', True),
            })
            if not site_created:
                for key, value in values.items():
                    setattr(site, key, value)
                fields = list(values)
                # 显式撤回授权立即停用；True/缺省均不得恢复人工暂停。
                if item.get('enabled') is False:
                    site.enabled = False
                    fields.append('enabled')
                site.save(update_fields=fields)
        # 校对后撤销的错误官网停止轮询，已有审计原文保留在后台。
        OfficialSite.objects.filter(entry=entry).exclude(url__in=approved_urls).update(enabled=False)
    return count


def bind_official_competition(competition, adapter_key):
    code = ADAPTER_CATALOG.get(adapter_key)
    if not code:
        return None
    entry = CatalogEntry.objects.filter(code=code).first()
    if entry is None:
        return None
    binding, _ = CatalogBinding.objects.get_or_create(entry=entry, competition=competition, defaults={
        'basis': f'已核实官方适配器 {adapter_key} 对应目录赛事系列；子赛具体奖项认定以学校当年规定为准。',
    })
    return binding
