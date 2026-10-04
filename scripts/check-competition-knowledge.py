"""Validate the public competition corpus against its evidence and delivery files."""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from curation.product import digest, make_chunks

# Editorial language is checked in prose, never by blindly banning a real school
# name from organizer names, entry restrictions or official source URLs.
EDITORIAL = re.compile(
    r'草稿待审核|仅供参考|字段映射|入库说明|后续开发|待人工|待补核|'
    r'已核验|已核实|核对到|须另核|尚未核实|加载失败|目录原名保留|'
    r'不声称|不表示现在|不能据标题|现阶段可核验|访问条件需确认|'
    r'已打开|未全部下载|未进一步核查|详细下载服务权限另核|'
    r'不是组委会指定教材|不视为公共资源|不把2027挑战赛当作|'
    r'校内安排(?:不套用到|不能直接用于)同济|套用于同济|'
    r'不写成全球统一|结构化报名|直接页面正文空|团队所属|来自同济|我们来自|同济2026-|tongji-2026-', re.I)


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def check(public, maintenance):
    corpus = load(public / 'corpus.json')
    records = corpus['records']
    outcomes = load(maintenance / 'processing-report.json')['outcomes']
    samples = load(public / 'samples.json')['records']
    errors = []

    def require(ok, message):
        if not ok:
            errors.append(message)

    require(len(outcomes) == 255, 'inventory_count')
    require(len({o['catalog_code'] for o in outcomes}) == 255, 'inventory_duplicates')
    require(len({r['id'] for r in records}) == len(records), 'record_duplicates')
    require(corpus['version'] == digest(records)[:16], 'corpus_version')
    by_id = {r['id']: r for r in records}
    for outcome in outcomes:
        actual = {r['id'] for r in records if outcome['catalog_code'] in r['catalog_codes']}
        require(actual == set(outcome['record_ids']), outcome['catalog_code'] + ':inventory_mapping')
        require(outcome['result'] == ('product' if actual else 'internal'), outcome['catalog_code'] + ':disposition')
        require(bool(actual or outcome.get('reasons')), outcome['catalog_code'] + ':missing_reason')

    prose = []
    for row in records:
        code = row['id']
        require(row['content_hash'] == digest({k: v for k, v in row.items() if k != 'content_hash'}), code + ':hash')
        source_ids = {s['id'] for s in row['sources']}
        require(bool(source_ids), code + ':sources')
        for source in row['sources']:
            require(bool(source.get('url', '').startswith(('http://', 'https://')) and
                         source.get('locator') and source.get('verified_at')), code + ':source_metadata')
            if source.get('verified_at'):
                try:
                    date.fromisoformat(source['verified_at'])
                except ValueError:
                    errors.append(code + ':source_date')
            prose.append((code + ':source_locator:' + source['id'], source.get('locator', '')))
        for key, value in row['fields'].items():
            refs = set(row['field_evidence'].get(key, []))
            require(bool(refs) and refs <= source_ids, code + ':field_evidence:' + key)
            if key in {'registration_start', 'registration_deadline', 'submission_deadline'}:
                try:
                    date.fromisoformat(value)
                except (TypeError, ValueError):
                    errors.append(code + ':field_date:' + key)
        require(len({s['id'] for s in row['sections']}) == len(row['sections']), code + ':section_duplicates')
        for section in row['sections']:
            require(bool(section['text'].strip()), code + ':empty_section')
            refs = set(section['evidence_ids'])
            require(bool(refs) and refs <= source_ids, code + ':section_evidence:' + section['id'])
            prose.append((code + ':' + section['id'], section['text']))
        prose.extend((code + ':' + key, row.get(key, '')) for key in ('title', 'edition', 'summary'))
        prose.extend((code + ':resource', r['title'] + '\n' + r['summary']) for r in row.get('learning_resources', []))
    for resource in load(public / 'learning-resources.json')['resources']:
        prose.append((resource['id'] + ':resource_body', resource.get('text', '')))
    for key, text in prose:
        match = EDITORIAL.search(text)
        if match:
            errors.append(key + ':editorial:' + match[0])
    require(len(samples) == 20, 'sample_count')
    require(len({r['catalog_code'] for r in samples}) == 20, 'sample_series_duplicates')
    require(all(r == by_id.get(r['id']) for r in samples), 'sample_content')
    sample_batches = {0 if int(r['catalog_code'][-3:]) <= 89 else 1 if int(r['catalog_code'][-3:]) <= 130 else 2 for r in samples}
    require(sample_batches == {0, 1, 2}, 'sample_batch_coverage')
    chunks = [json.loads(line) for line in (public / 'chunks.jsonl').read_text(encoding='utf-8').splitlines() if line]
    require(chunks == make_chunks(records), 'chunk_content')
    version = load(public / 'version.json')
    require(version['version'] == corpus['version'] and version['record_count'] == len(records)
            and version['chunk_count'] == len(chunks), 'version_manifest')
    return {'ok': not errors, 'corpus_version': corpus['version'], 'catalogs': len(outcomes),
            'dispositions': dict(Counter(o['result'] for o in outcomes)), 'records': len(records),
            'samples': len(samples), 'chunks': len(chunks), 'errors': errors}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', type=Path, default=ROOT / 'docs/competition-knowledge')
    parser.add_argument('--maintenance', type=Path, default=ROOT / 'docs/competition-knowledge-maintenance')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = check(args.public, args.maintenance)
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    print(text)
    raise SystemExit(0 if report['ok'] else 1)
