"""Build the neutral competition library from local, preserved research inputs."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from curation.product import (build_edition_record, build_overview_record, clean_text,
                              digest, make_chunks, record_text, render_resource, add_discovery_metadata,
                              resource_prose, prepare_resource, add_explicit_study_filters)
from curation.product import fact_heading, product_title


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')


def merge_record(records, record):
    old = records.get(record['id'])
    if old:
        old['catalog_codes'] = sorted(set(old.get('catalog_codes', [old['catalog_code']]) + record.get('catalog_codes', [record['catalog_code']])))
        if record['title'] != old['title'] and record['title'] not in old['aliases']:
            old['aliases'].append(record['title'])
        old['content_hash'] = digest({k: v for k, v in old.items() if k != 'content_hash'})
    else:
        records[record['id']] = record


def display_sections(record):
    groups = {}
    for section in record['sections']:
        if section['id'] == 'field-eligibility' and any(s['id'] == 'verified-eligibility' for s in record['sections']):
            continue
        if record['catalog_code'] == '2026090' and section['id'] == 'fact-1' and any(s['id'] == 'verified-eligibility' for s in record['sections']):
            continue
        heading = section['heading']
        if any(word in heading for word in ('对象', '资格')):
            heading = '参赛对象'
        elif any(word in heading for word in ('组队', '人数', '参赛形式')):
            heading = '组队要求'
        elif any(word in heading for word in ('截止', '赛程', '时间', '报名开始')):
            heading = '重要时间'
        elif any(word in heading for word in ('报名', '入口')):
            heading = '报名方式'
        elif any(word in heading for word in ('赛道', '作品', '评分', '赛制')):
            heading = '赛道与作品要求'
        else:
            heading = '赛事简介'
        text = section['text']
        if section['id'].startswith('field-') and heading != section['heading']:
            text = section['heading'] + '：' + text
        normalized_raw = re.sub(r'\W', '', section['text'])
        if section['id'].startswith('field-') and any(
                normalized_raw in re.sub(r'\W', '', other['text'])
                for other in record['sections'] if not other['id'].startswith('field-')):
            continue
        texts = groups.setdefault(heading, [])
        normalized = re.sub(r'\W', '', text)
        if not any(normalized in re.sub(r'\W', '', old) for old in texts):
            texts.append(text)
    order = ('赛事简介', '参赛对象', '赛道与作品要求', '组队要求', '报名方式', '重要时间')
    return [(heading, '\n\n'.join(groups[heading])) for heading in order if groups.get(heading)]


def markdown_record(record):
    lines = ['## ' + record['title'], '', '**' + (record['edition'] or '赛事介绍') + '**', '']
    for heading, text in display_sections(record):
        lines.extend(['### ' + heading, '', text, ''])
    if record.get('learning_resources'):
        lines.extend(['### 学习资料', ''])
        for resource in record['learning_resources']:
            lines.extend(['- [' + resource['title'] + '](' + resource['url'] + ')',
                          '  ' + resource['summary'], ''])
    lines += ['### 官方来源', '']
    for source in record['sources']:
        lines.append('- [' + source['title'] + '](' + source['url'] + ') · ' + source['locator'])
    return '\n'.join(lines) + '\n'


def html_library(records, as_of):
    escape = html.escape
    cards = []
    for record in records:
        text = ' '.join([record['title'], record['edition'], *record['aliases'], *[s['text'] for s in record['sections']]])
        sections = ''.join('<section><h3>' + escape(heading) + '</h3><p>' + escape(text).replace('\n', '<br>') + '</p></section>' for heading, text in display_sections(record))
        if record.get('learning_resources'):
            sections += '<section><h3>学习资料</h3><ul>' + ''.join('<li><a target="_blank" rel="noopener noreferrer" href="' + escape(r['url'], quote=True) + '">' + escape(r['title']) + '</a><p>' + escape(r['summary']) + '</p></li>' for r in record['learning_resources']) + '</ul></section>'
        sources = ''.join('<li><a target="_blank" rel="noopener noreferrer" href="' + escape(s['url'], quote=True) + '">' + escape(s['title']) + '</a><small>' + escape(s['locator']) + '</small></li>' for s in record['sources'])
        cards.append('<details class="card" data-search="' + escape(text.casefold(), quote=True) + '"><summary><strong>' + escape(record['title']) + '</strong><span>' + escape(record['edition'] or '赛事介绍') + '</span></summary><div class="body">' + sections + '<section><h3>官方来源</h3><ul>' + sources + '</ul></section></div></details>')
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>赛事指南 · 创享</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f2f5f9;color:#172b46;font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1060px;margin:auto;padding:46px 24px 80px}h1{font-size:36px;margin:0}header p{color:#536782}input{width:100%;font:inherit;padding:14px 18px;border:1px solid #c8d5e5;border-radius:10px;background:white}nav{position:sticky;top:0;background:#f2f5f9ee;padding:16px 0;backdrop-filter:blur(8px)}#count{font-size:14px;color:#536782;margin:4px 0 18px}.card{border:1px solid #d8e2ed;background:white;border-radius:12px;margin:12px 0;overflow:hidden}summary{padding:20px;cursor:pointer;list-style:none}summary strong{display:block;font-size:18px}summary span,small{display:block;color:#667a95;font-size:13px}.body{padding:0 24px 24px;border-top:1px solid #e3eaf2}h3{font-size:16px;margin-bottom:4px}p{margin-top:4px}a{color:#2259ae;overflow-wrap:anywhere}li{margin:9px 0}footer{color:#667a95;font-size:13px;margin-top:30px}@media(max-width:600px){main{padding:25px 14px}h1{font-size:29px}.body{padding:0 16px 18px}summary{padding:16px}}</style>
<main><header><h1>赛事指南</h1><p>查找赛事要求、报名方式与学习方向。按赛事名称或关键词搜索，展开查看详情。</p></header><nav><input id="search" type="search" aria-label="搜索赛事" placeholder="搜索赛事名称、主题或技能"></nav><p id="count"></p>''' + ''.join(cards) + '<footer>资料日期：' + escape(as_of) + '''</footer></main><script>const cards=[...document.querySelectorAll('.card')],input=document.querySelector('#search');function update(){const q=input.value.trim().toLocaleLowerCase();let n=0;for(const card of cards){card.hidden=!card.dataset.search.includes(q);if(!card.hidden)n++}document.querySelector('#count').textContent=`共 ${n} 条赛事资料`}input.addEventListener('input',update);update()</script></html>'''


def apply_supplements(records, supplements):
    for item in supplements.get('records', []):
        matches = [r for r in records.values() if item['catalog_code'] in r.get('catalog_codes', [r['catalog_code']]) and r['edition'] == item['edition']]
        if item.get('code'):
            matches = [records[item['code']]] if item['code'] in records else []
        previous = matches[0] if matches else None
        code = item.get('code') or (previous['code'] if previous else 'verified-' + item['catalog_code'] + '-' + digest(item['edition'])[:10])
        record = dict(previous or {'id': code, 'code': code, 'catalog_code': item['catalog_code'],
                                  'catalog_codes': [item['catalog_code']], 'competition_id': None,
                                  'title': item['title'], 'edition': item['edition'], 'category': '',
                                  'level': 'unknown', 'aliases': [], 'fields': {}, 'field_evidence': {},
                                  'sources': [], 'sections': [], 'kind': 'edition'})
        sources = item.get('sources', [])
        ids = {s['id'] for s in sources}
        if not sources or any(not s.get('url') or not s.get('verified_at') or not s.get('locator') for s in sources):
            raise ValueError('Supplement sources require URL, locator and actual verification date: ' + code)
        if any(not s.get('evidence_ids') or not set(s['evidence_ids']) <= ids for s in item.get('sections', [])):
            raise ValueError('Supplement section lacks evidence: ' + code)
        for field in item.get('fields', {}):
            if not item.get('field_evidence', {}).get(field) or not set(item['field_evidence'][field]) <= ids:
                raise ValueError('Supplement field lacks evidence: ' + code + '/' + field)
        for key in ('title', 'edition', 'category', 'level', 'aliases'):
            if key in item:
                record[key] = item[key]
        previous_sections = [] if item.get('replace_sections') else [
            section for section in record.get('sections', [])
            if section['id'] not in {'field-' + name for name in item.get('fields', {})}
            and section['id'] not in item.get('supersedes_sections', [])]
        record['sections'] = list({section['id']: section for section in
                                  [*previous_sections, *item.get('sections', [])]}.values())
        for key in ('fields', 'field_evidence'):
            record[key] = {**({} if item.get('replace_fields') else record.get(key, {})), **item.get(key, {})}
        record['sources'] = list({s['id']: s for s in [*record.get('sources', []), *sources]}.values())
        record['kind'] = item.get('kind', 'edition')
        record['summary'] = item.get('summary') or record['sections'][0]['text']
        record['review_status'] = 'approved'
        record['publication_status'] = 'published'
        record['content_hash'] = digest({k: v for k, v in record.items() if k != 'content_hash'})
        records[code] = record


def build(args):
    output = args.output.resolve()
    maintenance = args.maintenance.resolve()
    output.mkdir(parents=True, exist_ok=True)
    maintenance.mkdir(parents=True, exist_ok=True)
    revisions_path = maintenance / 'public-text-revisions.json'
    revisions = load(revisions_path) if revisions_path.is_file() else {}
    inputs = [(args.package_1.resolve(), '001-089'), (args.package_2.resolve(), '090-130'), (args.package_3.resolve(), '131-255')]
    records, outcomes, mappings, originals, resources, categories = {}, [], [], [], {}, {}
    for path, batch in inputs:
        canonical = load(path / '整理底稿.json')
        manifest = load(path / '导入清单.json')
        existing_competition_codes = {row['code'] for row in manifest.get('competitions', [])}
        existing_competition_codes.update(row['code'] for row in manifest.get('references', {}).get('competitions', []))
        categories.update({category['code']: category for category in canonical.get('competition_categories', [])})
        # Preserve original evidence and metadata without rewriting source packs.
        for filename in ('整理底稿.json', '导入清单.json', '附件清单.json'):
            source = path / filename
            if source.is_file():
                snapshot = maintenance / 'source-snapshots' / batch / filename
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                snapshot.write_bytes(source.read_bytes())
                originals.append({'batch': batch, 'file': f'source-snapshots/{batch}/{filename}', 'snapshot': snapshot.relative_to(maintenance).as_posix(),
                                  'sha256': __import__('hashlib').sha256(source.read_bytes()).hexdigest()})
        excluded = set(canonical.get('work_scope', {}).get('deferred_numbers', []))
        if batch == '131-255':
            excluded |= {139, 160, 165, 171, 200, 226, 245, 247, 253}
        for entry in canonical['entries']:
            produced, reasons = [], []
            if batch == '001-089':
                record, reason = build_overview_record(entry, entry.get('checked_on') or canonical['checked_on'])
                if record:
                    merge_record(records, record)
                    produced.append(record['id'])
                    mappings.append({'record_id': record['id'], 'package_id': manifest['package_id'], 'document_code': record['code'], 'competition_code': None})
                elif reason:
                    reasons.append(reason)
            else:
                for edition in entry['editions']:
                    record, reason = build_edition_record(entry, edition)
                    if record:
                        merge_record(records, record)
                        produced.append(record['id'])
                        mappings.append({'record_id': record['id'], 'package_id': manifest['package_id'], 'document_code': 'doc-' + edition['id'],
                                         'competition_code': record['code'] if record['code'] in existing_competition_codes else None})
                    elif reason:
                        reasons.append(edition['id'] + ':' + reason)
            outcomes.append({'catalog_code': entry['code'], 'title': entry['name'], 'batch': batch,
                             'result': 'product' if produced else 'internal', 'record_ids': produced,
                             'reasons': reasons, 'original_gaps': entry.get('gaps', [])})
        # Learning links remain clearly separate from competition requirements.
        if batch == '001-089':
            candidates = [(entry['code'], r) for entry in canonical['entries'] for r in entry['learning_resources']
                          if r.get('verified_by') == 'page_read']
        else:
            by_id = {r['id']: r for r in canonical.get('resources', [])}
            candidates = [(entry['code'], by_id[link['resource_id']]) for entry in canonical['entries']
                          for link in entry['learning']]
        for catalog_code, resource in candidates:
            identity = 'resource-' + digest([resource['url'], resource['title']])[:20]
            resource = {**resource, **revisions.get('resource_titles', {}).get(resource['title'], {})}
            for key, value in resource.items():
                if isinstance(value, str):
                    for old, new in revisions.get('resource_text_replacements', {}).items():
                        value = value.replace(old, new)
                    resource[key] = value
            resource = prepare_resource(resource)
            text = render_resource(resource)
            if not resource_prose(resource.get('summary', '')):
                continue
            row = resources.setdefault(identity, {'id': identity, 'title': resource['title'], 'url': resource['url'],
                                                   'text': text, 'summary': resource_prose(resource['summary']), 'catalog_codes': [], 'provider': resource.get('provider', ''),
                                                   'verified_at': resource.get('checked_on') or canonical.get('checked_on')})
            if catalog_code not in row['catalog_codes']:
                row['catalog_codes'].append(catalog_code)
    supplements = args.supplements or maintenance / 'verified-supplements.json'
    if supplements.is_file():
        apply_supplements(records, load(supplements))
    rechecked = maintenance / 'rechecked-supplements.json'
    if rechecked.is_file():
        apply_supplements(records, load(rechecked))
    temporal = maintenance / 'temporal-supplements.json'
    if temporal.is_file():
        apply_supplements(records, load(temporal))
    for code, record in list(records.items()):
        if record['catalog_code'] in revisions.get('internal', {}) or code in revisions.get('internal_records', {}):
            del records[code]
            continue
        changes = {**revisions.get('record_sections', {}).get(record['catalog_code'], {}),
                   **revisions.get('edition_sections', {}).get(record['id'], {})}
        if record['catalog_code'] == '2026248' and not record['edition'].startswith('2025'):
            changes = {}
        for section in record['sections']:
            if section['id'] in changes:
                section['text'] = changes[section['id']] or ''
            else:
                section['text'] = clean_text(section['text'])
            section['text'] = revisions.get('record_text_replacements', {}).get(section['text'], section['text'])
            if section['id'].startswith('fact-'):
                section['heading'] = fact_heading(section['text'])
        for field, value in list(record['fields'].items()):
            value = revisions.get('field_replacements', {}).get(record['catalog_code'], {}).get(field, value)
            if isinstance(value, str):
                record['fields'][field] = clean_text(value)
                for section in record['sections']:
                    if section['id'] == 'field-' + field and field in revisions.get('field_replacements', {}).get(record['catalog_code'], {}):
                        section['text'] = record['fields'][field]
            if not record['fields'][field] or field in revisions.get('drop_fields', {}).get(record['catalog_code'], []):
                record['fields'].pop(field)
                record['field_evidence'].pop(field, None)
                record['sections'] = [s for s in record['sections'] if s['id'] != 'field-' + field]
        record['sections'] = [s for s in record['sections'] if s['text']]
        if not record['sections']:
            del records[code]
            continue
        record['summary'] = record['sections'][0]['text']
        add_explicit_study_filters(record['fields'], record['field_evidence'])
        used = {sid for ids in record['field_evidence'].values() for sid in ids}
        used.update(sid for section in record['sections'] for sid in section['evidence_ids'])
        record['sources'] = [s for s in record['sources'] if s['id'] in used]
    rows = sorted(records.values(), key=lambda r: (r['catalog_code'], r['edition'], r['id']))
    public_catalogs = {catalog_code for row in rows for catalog_code in row['catalog_codes']}
    resources = {key: resource for key, resource in resources.items()
                 if resource['title'] and set(resource['catalog_codes']) & public_catalogs}
    for row in rows:
        row.update(revisions.get('record_metadata', {}).get(row['catalog_code'], {}))
        row['sources'] = list({source['id']: source for source in row['sources']}.values())
        for source in row['sources']:
            source['title'] = revisions.get('source_titles', {}).get(source['title'], source['title'])
            source.update(revisions.get('source_metadata', {}).get(source['url'], {}))
            source['locator'] = revisions.get('source_locator_replacements', {}).get(source['locator'], source['locator'])
        row['field_evidence'] = {key: list(dict.fromkeys(ids)) for key, ids in row['field_evidence'].items()}
        for section in row['sections']:
            section['evidence_ids'] = list(dict.fromkeys(section['evidence_ids']))
        add_discovery_metadata(row, categories)
        row['title'] = product_title(row['title'], row['edition'], row['id'])
        excluded_resources = set(revisions.get('edition_resource_exclusions', {}).get(row['id'], []))
        row['learning_resources'] = [{k: r[k] for k in ('id', 'title', 'url', 'summary')} for r in resources.values()
                                     if set(row['catalog_codes']) & set(r['catalog_codes']) and r['id'] not in excluded_resources]
        row['content_hash'] = digest({k: v for k, v in row.items() if k != 'content_hash'})
    for outcome in outcomes:
        outcome['record_ids'] = [r['id'] for r in rows if outcome['catalog_code'] in r.get('catalog_codes', [r['catalog_code']])]
        outcome['result'] = 'product' if outcome['record_ids'] else 'internal'
        if outcome['catalog_code'] in revisions.get('internal', {}):
            outcome['reasons'] = [revisions['internal'][outcome['catalog_code']]]
    recheck_report = maintenance / 'recheck-review.json'
    if recheck_report.is_file():
        reviews = {row['catalog_code']: row for row in load(recheck_report)['records']}
        for outcome in outcomes:
            if outcome['catalog_code'] in reviews:
                outcome['recheck'] = reviews[outcome['catalog_code']]
                outcome['reasons'] = [reviews[outcome['catalog_code']]['conclusion']]
    assert len(outcomes) == 255 and len({o['catalog_code'] for o in outcomes}) == 255
    corpus = {'schema_version': 1, 'version': digest(rows)[:16], 'as_of': args.as_of, 'records': rows}
    chunks = make_chunks(rows)
    write_json(output / 'corpus.json', corpus)
    write_jsonl(output / 'chunks.jsonl', chunks)
    write_json(output / 'learning-resources.json', {'schema_version': 1, 'resources': list(resources.values())})
    write_json(output / 'categories.json', list(categories.values()))
    write_json(output / 'sources.json', list({s['id']: s for r in rows for s in r['sources']}.values()))
    write_json(output / 'version.json', {k: corpus[k] for k in ('schema_version', 'version', 'as_of')} |
               {'record_count': len(rows), 'catalog_count': sum(o['result'] == 'product' for o in outcomes), 'chunk_count': len(chunks)})
    write_json(maintenance / 'processing-report.json', {'as_of': args.as_of, 'outcomes': outcomes})
    write_json(maintenance / 'source-manifest.json', originals)
    write_json(maintenance / 'product-mapping.json', mappings)
    write_json(maintenance / 'field-coverage.json', {'records': len(rows), 'fields': dict(Counter(k for r in rows for k in r['fields'])),
                                                   'categorized': sum(bool(r['category']) for r in rows),
                                                   'with_aliases': sum(bool(r['aliases']) for r in rows),
                                                   'alias_count': sum(len(r['aliases']) for r in rows)})
    with (output / 'competitions.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        columns = ['名称', '届次', '简介', '参赛对象', '参赛形式', '最少人数', '最多人数', '报名截止', '提交截止', '报名入口', '来源']
        writer = csv.writer(stream)
        writer.writerow(columns)
        for row in rows:
            fields = row['fields']
            writer.writerow([row['title'], row['edition'], row['summary'], fields.get('eligibility', ''),
                             fields.get('participation_type', ''), fields.get('team_size_min', ''),
                             fields.get('team_size_max', ''), fields.get('registration_deadline', ''),
                             fields.get('submission_deadline', ''), fields.get('registration_url', ''),
                             ' | '.join(dict.fromkeys(s['url'] for s in row['sources']))])
    (output / '赛事指南.md').write_text('# 赛事指南\n\n' + '\n'.join(markdown_record(r) for r in rows), encoding='utf-8')
    (output / 'index.html').write_text(html_library(rows, args.as_of), encoding='utf-8')
    sample_numbers = [20, 34, 47, 74, 90, 92, 100, 101, 108, 113, 135, 141, 156, 173, 179, 186, 214, 244, 164, 148]
    samples, used = [], set()
    for number in sample_numbers:
        matches = [r for r in rows if str(2026000 + number) in r['catalog_codes']]
        if matches:
            samples.append(matches[-1]); used.add(matches[-1]['id'])
    used_catalogs = {r['catalog_code'] for r in samples}
    for row in sorted(rows, key=lambda r: (-len(r['fields']), r['catalog_code'])):
        if len(samples) >= 20:
            break
        if row['id'] not in used and row['catalog_code'] not in used_catalogs and row['kind'] == 'edition':
            samples.append(row); used.add(row['id'])
            used_catalogs.add(row['catalog_code'])
    write_json(output / 'samples.json', {'schema_version': 1, 'records': samples})
    (output / '20项样本.md').write_text('# 赛事样本\n\n' + '\n'.join(markdown_record(r) for r in samples), encoding='utf-8')
    print(json.dumps({'records': len(rows), 'catalogs': sum(o['result'] == 'product' for o in outcomes),
                      'internal': sum(o['result'] == 'internal' for o in outcomes), 'chunks': len(chunks),
                      'resources': len(resources), 'version': corpus['version']}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    snapshots = ROOT / 'docs/competition-knowledge-maintenance/source-snapshots'
    parser.add_argument('--package-1', type=Path, default=snapshots / '001-089')
    parser.add_argument('--package-2', type=Path, default=snapshots / '090-130')
    parser.add_argument('--package-3', type=Path, default=snapshots / '131-255')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/competition-knowledge')
    parser.add_argument('--maintenance', type=Path, default=ROOT / 'docs/competition-knowledge-maintenance')
    parser.add_argument('--supplements', type=Path)
    parser.add_argument('--as-of', default='2026-10-04')
    build(parser.parse_args())
