"""从人工底稿生成 curation v1 离线包；仅本地转换，不访问网站、不写数据库。"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKAGE_ID = 'tongji-2026-001-089-20261003'
source = json.loads((HERE / '整理底稿.json').read_text(encoding='utf-8'))
rows = source['entries']
assert [r['code'] for r in rows] == [str(2026000 + n) for n in range(1, 90)]
catalog_data = json.loads((ROOT / 'backend/competition_catalog/data/tongji-2026.json').read_text(encoding='utf-8'))
catalog = {row['code']: row for row in catalog_data['entries']}
types = {'rules': '规则与模板', 'problems': '赛题与样题', 'course': '课程与教程',
         'examples': '作品与案例', 'tools': '技术工具', 'dataset': '数据集', 'code': '示例代码'}
levels = {'page_read': '已读来源页面（不代表附件全文已读）',
          'official_index': '已确认索引或入口，资料正文待核对', 'search_result': '仅搜索结果，正文待核对'}
uncertain = {'2026052', '2026057', '2026063', '2026064', '2026067'}


def source_state(row):
    if row['code'] in uncertain:
        return 'name_uncertain'
    if not any(s['verified_by'] in ('page_read', 'official_index') for s in row['competition_sources']):
        return 'unconfirmed'
    return 'confirmed'


def write_json(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


documents, resources, ledger = [], {}, []
for row in rows:
    code = row['code']
    assert row['name'] == catalog[code]['name']
    metadata = {'content_type': 'manual_summary', 'contains_source_fulltext': False,
                'checked_on': row['checked_on'], 'edition_note': row['edition_note'],
                'source_status': source_state(row), 'gaps': row['gaps'], 'research_code': code}
    paragraphs = ['人工整理摘要，非来源全文。', row['edition_note'], row['overview'], '赛事来源：']
    for s in row['competition_sources']:
        paragraphs.append(f"{s['title']}\n{s['url']}\n提供方：{s['provider']}；核验程度：{levels[s['verified_by']]}\n{s['summary']}")
        ledger.append({'catalog_code': code, 'resource_group': 'competition', **s})
    paragraphs.extend(['待补内容：', *row['gaps']])
    documents.append({'code': f'm89-{code}-overview', 'title': row['name'] + '｜赛事资料档案',
                      'body': '\n\n'.join(paragraphs), 'edition': '',
                      'catalog_codes': [code], 'competition_codes': [], 'resource_codes': [],
                      'sources': row['competition_sources'], 'attachments': [], 'metadata': metadata})
    for s in row['learning_resources']:
        # 不同附件可共用索引 URL；不能仅按链接合并掉不同资料。
        key = (s['url'], s['type'], s['title'])
        identifier = hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()[:20]
        resource_code = 'm89-resource-' + identifier
        if key not in resources:
            resources[key] = {'code': resource_code, 'catalog_codes': [], 'competition_codes': [],
                              'fields': {'title': s['title'], 'provider': s['provider'], 'access_url': s['url'],
                                         'availability': 'available',
                                         'source_note': '人工整理的外链资源草稿；访问条件与核验程度见介绍和关联知识档案，未逐份下载原文。'},
                              '_contexts': []}
        resource = resources[key]
        if code not in resource['catalog_codes']:
            resource['catalog_codes'].append(code)
        context = (f"{row['code']} {row['name']}\n类型：{types[s['type']]}；难度：{s['level']}；访问：{s['access']}\n"
                   f"核验程度：{levels[s['verified_by']]}\n适用：{s['applies_to']}\n用途：{s['why_useful']}\n{s['summary']}")
        resource['_contexts'].append(context)
        documents.append({'code': f'm89-{code}-learning-{identifier}', 'title': row['name'] + '｜' + s['title'],
                          'body': '人工整理的学习导读，非资料原文。\n\n' + row['edition_note'] + '\n\n' + context,
                          'edition': '', 'catalog_codes': [code], 'competition_codes': [],
                          'resource_codes': [resource_code], 'sources': [s], 'attachments': [],
                          'metadata': {**metadata, 'resource_type': s['type'], 'access': s['access'],
                                       'verified_by': s['verified_by'], 'level': s['level'],
                                       'applies_to': s['applies_to'], 'why_useful': s['why_useful']}})
        ledger.append({'catalog_code': code, 'resource_group': 'learning', **s})

resource_rows = []
for resource in resources.values():
    resource['fields']['description'] = '\n\n'.join(resource.pop('_contexts'))
    assert len(resource['fields']['description']) <= 10000
    resource_rows.append(resource)
assert len(documents) == 301 and len(resource_rows) == 207
data = {'schema_version': 1, 'package_id': PACKAGE_ID,
        'catalog_scope': {'first': 1, 'last': 89, 'batch_size': 25},
        'prepared_on': source['checked_on'],
        'review': {'status': 'pending'},
        'work_scope': {'catalog_count': 89, 'deferred_numbers': [],
                       'note': '只生成目录、学习资源及人工摘要知识档案；尚未将报名规则整理为单一实际届次，不创建Competition。'},
        'catalog': [{**{k: catalog[r['code']][k] for k in ('code', 'name', 'grade', 'levels', 'departments')},
                     'source_url': catalog_data['source_url']} for r in rows],
        'competitions': [], 'resources': resource_rows, 'documents': documents}
write_json('导入清单.json', data)
write_json('来源清单.json', ledger)
write_json('附件清单.json', {'attachments': [], 'note': '本批交付摘要和外链，未交付网页/PDF/视频等原件，不将链接计作已下载附件。'})
report = {'package_id': PACKAGE_ID, 'counts': {key: len(data[key]) for key in ('catalog', 'competitions', 'resources', 'documents')},
          'research_counts': source['counts'],
          'source_status_counts': {state: sum(source_state(r) == state for r in rows)
                                  for state in ('confirmed', 'name_uncertain', 'unconfirmed')},
          'batches': [{'batch': n, 'first': first, 'last': last, 'catalog': last - first + 1}
                      for n, (first, last) in enumerate(((1, 25), (26, 50), (51, 75), (76, 89)), 1)],
          'notes': ['207项资源按URL、类型、标题去重；212条学习导读保留各赛事的适用范围。',
                    '301份知识档案为89份赛事摘要与212份学习导读，不是301份来源全文。',
                    '所有入库对象均为草稿；不自动公开或纳入AI问答。']}
write_json('批次报告.json', report)
for kind in ('catalog', 'competitions', 'resources', 'documents'):
    folder = HERE / '导入数据'
    folder.mkdir(exist_ok=True)
    (folder / f'{kind}.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in data[kind]), encoding='utf-8')
print(json.dumps(report['counts'], ensure_ascii=False))
