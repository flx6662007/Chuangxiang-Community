"""Generate an offline research delivery from its canonical JSON; never fetch or publish."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


STATUS = {'rules': '已取得规则或正式通知', 'partial': '细则有缺口',
          'report': '仅有报道', 'identity': '赛事身份未确认'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf8')).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')


def resource_text(resource):
    labels = {'summary': '中文摘要', 'audience': '适用对象', 'prerequisites': '基础要求',
              'how_to_start': '入门顺序', 'language': '语言', 'access': '访问条件',
              'scope': '适用范围', 'url': '来源链接', 'provider': '发布方',
              'locator': '来源定位', 'checked_on': '核验日期'}
    return resource['title'] + '\n' + '\n'.join(f'{label}：{resource[key]}' for key, label in labels.items())


def resource_source(resource):
    return dict(url=resource['url'], title=resource['title'], publisher=resource['provider'],
                checked_on=resource['checked_on'], published_on=resource.get('published_on'),
                locator=resource['locator'], access=resource['access'])


def attachment_urls(attachment):
    return {attachment['url'], *attachment.get('url_aliases', [])}


def build(filename, dependency=None):
    root = filename.resolve().parent
    data = json.loads(filename.read_text(encoding='utf-8-sig'))
    scope = data['catalog_scope']
    entries = data['entries']
    assert {e['number'] for e in entries} == set(range(scope['start'], scope['end'] + 1))
    resources = {r['id']: r for r in data['resources']}
    dependency_data = json.loads(dependency.read_text(encoding='utf-8-sig')) if dependency else {}
    owned = {kind: {r['code']: r for r in dependency_data.get(kind, [])}
             for kind in ('competitions', 'resources')}
    manifest = dict(schema_version=1, package_id=data['package_id'], catalog_scope=scope,
                    review=data['review'], catalog=[], competitions=[], resources=[], documents=[],
                    references={'competitions': [], 'resources': []}, dependencies=data.get('dependencies', []))
    refs = {'competitions': {}, 'resources': {}}
    competition_rows = {}
    resource_uses = defaultdict(lambda: {'catalog_codes': set(), 'competition_codes': set()})
    index = []

    def reference(kind, code, catalog_code):
        if code not in owned[kind]:
            raise ValueError(f'Missing dependency payload: {kind}/{code}')
        if code not in refs[kind]:
            refs[kind][code] = dict(code=code, package_id=dependency_data['package_id'],
                                    payload_hash=digest(owned[kind][code]), catalog_codes=[])
        if catalog_code not in refs[kind][code]['catalog_codes']:
            refs[kind][code]['catalog_codes'].append(catalog_code)

    for entry in entries:
        code = entry['code']
        adopted = next(ed for ed in entry['editions'] if ed['id'] == entry['adopted_edition_id'])
        folder = root / '赛事档案' / code
        folder.mkdir(parents=True, exist_ok=True)
        manifest['catalog'].append({k: entry[k] for k in ('code', 'name', 'grade', 'levels', 'departments')}
                                   | {'source_url': data['catalog_source_url']})
        events = []
        for edition in entry['editions']:
            actual = entry['identity_status'] != 'unconfirmed' and edition['year'] is not None
            event_code = edition.get('competition_reference', 'curated-' + edition['id'])
            if entry['number'] in (122, 123):
                event_code = 'curated-shanghai-mechanics-2026-7'
            caveat = ('历史资料，不代表2026报名期限。' if edition['year'] and edition['year'] < 2026
                      else '只适用于所标届次；当届简讯与往届规则分开使用。')
            facts = '\n'.join(f"• {f['text']} [{f['source_id']}；{f['locator']}]" for f in edition['facts'])
            body = (f"目录：{code} {entry['name']}\n目录年份：2026\n资料届次：{edition['label']}\n"
                    f"{caveat}\n证据状态：{STATUS[edition['evidence_status']]}\n审核：草稿，待审核\n\n"
                    f"整理正文：\n{facts}\n\n字段映射（未知留空）：\n"
                    + json.dumps(edition['fields'], ensure_ascii=False, indent=2)
                    + '\n\n缺口：\n' + '\n'.join(edition['gaps']))
            efolder = folder / edition['id']
            efolder.mkdir(exist_ok=True)
            (efolder / '赛事说明.txt').write_text(body, encoding='utf8')
            write_json(efolder / '来源清单.json', edition['sources'])
            if actual:
                events.append(event_code)
                if edition.get('competition_reference'):
                    reference('competitions', event_code, code)
                elif event_code in competition_rows:
                    competition_rows[event_code]['catalog_codes'].append(code)
                else:
                    fields = dict(title=entry.get('current_name') or entry['name'], edition=edition['label'],
                                  summary=edition['summary'][:500], description=body)
                    fields.update(edition['fields'])
                    if entry['number'] in (122, 123):
                        fields['title'] = '第七届上海市大学生力学竞赛'
                    sources = [dict(source_type='campus' if '.edu.cn' in s['url'] else 'official',
                                    source_name=s['publisher'][:200], source_url=s['url'],
                                    source_published_on=s.get('published_on'), is_primary=i == 0)
                               for i, s in enumerate(edition['sources'])]
                    competition_rows[event_code] = dict(code=event_code, catalog_codes=[code], fields=fields, sources=sources)
            urls = {s['url'] for s in edition['sources']}
            attachments = [a for a in data['attachments'] if urls & attachment_urls(a)]
            manifest['documents'].append(dict(code='doc-' + edition['id'], title=entry['name'] + '｜' + edition['label'],
                body=body, edition=edition['label'], catalog_codes=[code], competition_codes=[event_code] if actual else [],
                resource_codes=[], sources=edition['sources'], attachments=attachments,
                metadata=dict(catalog_year=2026, historical=bool(edition['year'] and edition['year'] < 2026),
                              evidence_status=edition['evidence_status'], facts=edition['facts'],
                              requirements=edition.get('requirements', {}), gaps=edition['gaps'], review_status='pending')))
        learning = []
        guide_sources = []
        for link in entry['learning']:
            resource = resources[link['resource_id']]
            rcode = resource.get('database_reference', 'learn-' + resource['id'])
            if resource.get('database_reference'):
                reference('resources', rcode, code)
            else:
                resource_uses[resource['id']]['catalog_codes'].add(code)
                # Generic learning resources link catalogs through knowledge docs. Edition-specific resources
                # only link an event if the canonical source explicitly declares that relation.
                resource_uses[resource['id']]['competition_codes'].update(link.get('competition_codes', []))
            learning.append(f"{link['order']}. {resource_text(resource)}\n推荐理由：{link['reason']}\n")
            guide_sources.append(resource_source(resource))
        guide = f"{code} {entry['name']}\n采用：{adopted['label']}\n各份学习资料按自己的适用范围使用。\n\n" + '\n'.join(learning)
        (folder / '学习资料导读.txt').write_text(guide, encoding='utf8')
        retained = [a for a in data['attachments'] if code in a.get('catalog_codes', [])]
        manifest['documents'].append(dict(code='guide-' + code, title=entry['name'] + '｜学习资料导读', body=guide,
            catalog_codes=[code], competition_codes=[], resource_codes=[resources[l['resource_id']].get(
                'database_reference', 'learn-' + l['resource_id']) for l in entry['learning']], sources=guide_sources,
            attachments=[a for a in data['attachments'] if attachment_urls(a) & {s['url'] for s in guide_sources}],
            metadata={'review_status': 'pending', 'scope': '各资源分别标注实际届次或通用范围'}))
        if retained:
            manifest['documents'].append(dict(code='attachments-' + code, title=entry['name'] + '｜附件目录',
                body='原件按自身届次使用。提取文本未经逐字校对，关键条款的核对范围另注。\n' + '\n'.join(
                    a['original_filename'] + '\n' + a['path'] + '\n' + a.get('text_review_note', '') for a in retained),
                catalog_codes=[code], competition_codes=[], resource_codes=[], attachments=retained,
                sources=[dict(url=a['url'], title=a['original_filename'], checked_on=a['verified_on'],
                              locator='附件原件；关键事实见对应赛事正文') for a in retained], metadata={'review_status': 'pending'}))
        write_json(folder / '缺口与检索记录.json', dict(gaps=entry['gaps'], research=entry['research']))
        write_json(folder / '附件清单.json', retained)
        index.append(dict(code=code, name=entry['name'], grade=entry['grade'], departments='、'.join(entry['departments']),
            batch=entry['batch'], edition=adopted['label'], evidence=STATUS[adopted['evidence_status']],
            current_status=entry['current_edition_status'], resources=len(entry['learning']), review='待审核',
            gaps='；'.join(entry['gaps']), source=adopted['sources'][0]['url'],
            file=f'赛事档案/{code}/{adopted["id"]}/赛事说明.txt', registration=adopted['fields']))
    manifest['competitions'] = list(competition_rows.values())
    for rid, uses in resource_uses.items():
        resource = resources[rid]
        manifest['resources'].append(dict(code='learn-' + rid, catalog_codes=sorted(uses['catalog_codes']),
            competition_codes=sorted(uses['competition_codes']), fields=dict(title=resource['title'],
                description=resource_text(resource), provider=resource['provider'], access_url=resource['url'],
                source_note=resource['scope'] + '；核验 ' + resource['checked_on'], availability='available')))
    manifest['references'] = {kind: list(rows.values()) for kind, rows in refs.items()}
    write_json(root / '导入清单.json', manifest)
    write_json(root / '附件清单.json', data['attachments'])
    write_json(root / '索引数据.json', index)
    records = [{'type': kind, **row} for kind in ('catalog', 'competitions', 'resources', 'documents') for row in manifest[kind]]
    records.extend({'type': 'reference-' + kind, **row} for kind, rows in manifest['references'].items() for row in rows)
    (root / '导入底稿.jsonl').write_text('\n'.join(json.dumps(row, ensure_ascii=False) for row in records) + '\n', encoding='utf8')
    stats = dict(catalog_count=len(entries), edition_records=len(manifest['competitions']),
        reused_editions=len(refs['competitions']), new_resources=len(manifest['resources']), reused_resources=len(refs['resources']),
        unique_resources=len(data['resources']), learning_links=sum(len(e['learning']) for e in entries),
        documents=len(manifest['documents']), archived_attachments=len(data['attachments']),
        under_three_resources=[e['code'] for e in entries if len(e['learning']) < 3],
        identity_unconfirmed=[e['code'] for e in entries if e['identity_status'] == 'unconfirmed'],
        evidence_counts=dict(Counter(r['evidence'] for r in index)), full_research_acceptance=False,
        review_status='pending', local_acceptance=data.get('local_acceptance'))
    write_json(root / '交付统计.json', stats)
    for batch in sorted({e['batch'] for e in entries}):
        write_json(root / '批次报告' / f'第{batch}批-缺口.json', [r for r in index if r['batch'] == batch])
    (root / '开始阅读.txt').write_text(f"目录{scope['start']}—{scope['end']}，共{len(entries)}项。\n总索引.xlsx查看汇总，赛事档案按编号和实际届次保存。\n"
        '整理底稿.json是唯一维护源；导入清单和阅读版从底稿生成。\n正文已整理，但仍有公开细则及身份缺口，不能宣称全量完整规则验收。\n'
        '本地导入为草稿，不发布、不开放组队、不接入页面。\n', encoding='utf8')
    print(json.dumps(stats, ensure_ascii=False))
    return stats


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--dependency', type=Path, help='Previously delivered import manifest for object reuse')
    args = parser.parse_args()
    build(args.source, args.dependency)
