"""Validate curated research records and rebuild the database import package."""
import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, urldefrag

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'docs/research-national/20261007'
CARD_FIELDS = {'id', 'title', 'unit', 'summary', 'participation', 'evidenceNote', 'date', 'verifiedOn', 'sourceUrl'}


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def validate(data):
    assert data['scope'] == 'national' and data['publicationStatus'] == 'draft'
    records = data['records']
    assert records and len(records) <= 1000
    assert len({r['id'] for r in records}) == len(records), '编号重复'
    assert len({(r['institution'], r['name']) for r in records}) == len(records), '实体重复'
    assert len({r['sources'][0]['url'].rstrip('/') for r in records}) == len(records), '主来源重复'
    assert not re.search(r'同济|tongji|本校|我校', dump(data), re.I), '全国包含有范围外身份信息'
    for row in records:
        assert re.fullmatch(r'research-cn-[a-z0-9-]+', row['id'])
        assert row['institution'] and row['name'] and row['summary'] and row['field']
        assert row['reviewStatus'] in {'ready_for_review', 'source_unavailable'}
        date.fromisoformat(row['checkedOn'])
        if row['publishedOn']:
            assert date.fromisoformat(row['publishedOn']) <= date.fromisoformat(row['checkedOn'])
        assert row['sources']
        for source in row['sources']:
            url = urlparse(source['url'])
            assert url.scheme in {'http', 'https'} and url.hostname and url.hostname.endswith('.edu.cn')
            assert not url.username and not url.password
        if row['reviewStatus'] == 'ready_for_review':
            assert row['sources'][0]['readable'], '不可读取来源不能进入导入候选'
            readable_urls = {urldefrag(s['url'])[0] for s in row['sources'] if s['readable']}
            for links in row['display'].get('fieldLinks', {}).values():
                assert isinstance(links, list) and len(links) <= 3
                assert len({link['url'] for link in links}) == len(links), '同字段来源重复'
                for link in links:
                    assert link['label'].strip() and urldefrag(link['url'])[0] in readable_urls, '字段链接未关联已读取来源'
        else:
            assert row['reviewNote']
        recruitment = row['recruitment']
        if recruitment:
            assert recruitment['applicationUrl'] in {s['url'] for s in row['sources']}
            if recruitment['deadline']:
                date.fromisoformat(recruitment['deadline'])
    return records


def build_cards(records):
    cards = []
    for row in records:
        if row['reviewStatus'] != 'ready_for_review':
            continue
        recruitment = row['recruitment']
        display = row['display']
        card = {
            'id': row['id'], 'title': row['name'],
            'unit': row['institution'] + (' · ' + row['campus'] if row['campus'] else ''),
            'summary': display['summary'],
            'participation': display['recruitment'].get('roles', ''),
            'evidenceNote': '', 'date': row['publishedOn'] or '', 'verifiedOn': row['checkedOn'],
            'sourceUrl': row['sources'][0]['url'],
        }
        assert set(card) == CARD_FIELDS
        cards.append(card)
    profiles = {r['id']: {**{k:v for k,v in r['display'].items() if k != 'summary'},
                          'hasRecruitmentSource': bool(r['recruitment'])}
                for r in records if r['reviewStatus'] == 'ready_for_review'}
    sources = {r['id']: [{'url': s['url'], 'title': s['title'], 'verifiedOn': s['checkedOn']}
                        for s in r['sources'] if s['readable']]
               for r in records if r['reviewStatus'] == 'ready_for_review'}
    return {'scope': 'national', 'laboratories': cards, 'profiles': profiles, 'sources': sources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT)
    parser.add_argument('--check', action='store_true', help='验证数据及生成文件是否一致，不写入')
    args = parser.parse_args()
    data = json.loads((args.directory/'records.json').read_text(encoding='utf-8'))
    records = validate(data)
    cards = build_cards(records)
    report = {'checkedOn':data['checkedOn'], 'records':len(records), 'schools':len({r['institution'] for r in records}),
              'importable':len(cards['laboratories']), 'pending':sum(r['reviewStatus']=='source_unavailable' for r in records),
              'withRecruitmentEvidence':sum(bool(r['recruitment']) for r in records),
              'descriptionOnly':sum(not r['recruitment'] for r in records),
              'recruitmentStatuses':dict(Counter(r['recruitment']['status'] for r in records if r['recruitment'])),
              'byInstitution':dict(Counter(r['institution'] for r in records)),
              'checks':['编号、实体和主链接无重复','来源为高校官方域名','范围外身份词未检出','九字段卡片兼容','不可读取条目不进入导入候选','未知日期与资格未自动补齐'],
              'limits':['当前空缺未向各实验室逐一确认','未明确校外资格不视为允许或禁止','历史招募仅作研究背景资料','官方网页今后可能更新或失效']}
    outputs = {'research-cards.json': dump(cards)}
    for filename, content in outputs.items():
        target = args.directory / filename
        if args.check:
            assert target.read_text(encoding='utf-8') == content, f'{filename} 与 records.json 不一致，请重新生成'
        else:
            target.write_text(content,encoding='utf-8')
    print(dump(report))


if __name__ == '__main__':
    main()
