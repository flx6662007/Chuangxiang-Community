"""Bind independently authored questions to a fixed corpus, without running search."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / 'docs/competition-knowledge/corpus.json'
DEFAULT_OUTPUT = ROOT / 'docs/competition-evaluation'

# These years and statements were read from the source packages, not inferred
# from search results. An absent or changed fact fails the build for review.
HISTORICAL = {'2026094': '2022', '2026109': '2025', '2026155': '2025', '2026184': '2025'}
POSITIVE_FILTERS = {
    '2026148': ({'participation_type': 'team', 'team_size': 4}, '我们是4名学生组成的团队。'),
    '2026164': ({'education': '本科', 'team_size': 5}, '我们是5名本科生。'),
    '2026212': ({'participation_type': 'team', 'team_size': 3}, '我们3名学生组队。'),
    '2026229': ({'participation_type': 'team', 'team_size': 3}, '我们是3名学生组成的团队。'),
}
CONSTRAINTS = [
    ('2026090', 'dev', 'hard_filter_conflict', {'team_size': 21},
     ['21人想组队参加2026诵读中国，筛出符合人数规则的结果。', '全队二十一人一起朗诵，查2026诵读中国允许的团队。'],
     '学生团队为2—20人；21人不满足上限。', '2—20'),
    ('2026100', 'dev', 'qualification_conflict', {'education': '硕士'},
     ['硕士生想参加2026嵌入式系统专题赛，找满足学历的项目。', '已在读研究生，查2026嵌入式系统专题赛可接受的报名资格。'],
     '2026嵌入式系统专题赛仅限普通高校全日制在校本科生。', '本科'),
    ('2026092', 'dev', 'time_boundary', {'registration_status': 'open', 'education': '本科'},
     ['本科生查2026大广赛常规类别今天开放报名的结果。', '本科生查2026大广赛常规类别今天仍开放报名的结果。'],
     '常规类别2026-05-10至2026-06-12提交即报名；5月15日在窗口内，10月4日不在窗口内。', '5月10日'),
    ('2026108', 'dev', 'hard_filter_conflict', {'team_size': 7},
     ['七名学生能组成2026 ICC模拟法庭队伍吗？', '不含教练我们有7名学生，筛出2026 ICC满足人数规则的项目。'],
     '学生选手3—5人，7人总数包含教练，不能当作学生名额。', '研究员'),
    ('2026113', 'dev', 'hard_filter_conflict', {'team_size': 4},
     ['四名学生想参加2026地质技能竞赛，筛选符合人数的项目。', '我们4个人都做选手，查2026地质技能竞赛满足组队人数的结果。'],
     '地质技能竞赛每队3名学生。', '每队3人'),
    ('2026115', 'dev', 'hard_filter_conflict', {'team_size': 2},
     ['只有两名学生，筛选2026 CCE杯复合材料赛可报名的队伍规则。', '我们2个人做玻璃纤维板簧，找2026 CCE杯符合团队人数的结果。'],
     '2026 CCE杯每队3—5名学生，至少3名本科生。', '3—5'),
    ('2026143', 'dev', 'hard_filter_conflict', {'participation_type': 'team'},
     ['想以共同答题的团队参加2026 CCSP，筛出允许团队参赛的结果。', '找2026 CCSP中可以多人作为同一队共同编程的比赛。'],
     'CCSP是个人机试，集体报名缴费不代表共同答题。', '个人机试'),
    ('2026148', 'dev', 'hard_filter_conflict', {'team_size': 5},
     ['五名学生全部做选手，找2026软件创新大赛符合人数的项目。', '不算指导教师，学生团队有5人，筛选2026软件创新赛。'],
     '学生队长1名、其他学生不超过3名，即学生至多4人。', '队长1名'),
    ('2026164', 'dev', 'qualification_conflict', {'education': '硕士'},
     ['我是硕士生，筛选2026国地杯自然资源赛符合学历的项目。', '研究生身份，查2026国地杯允许报名的赛事结果。'],
     '2026国地杯面向全日制在校本专科学生。', '本专科'),
    ('2026097', 'dev', 'missing_data', {'team_size': 6},
     ['六名学生，未选择赛道，筛选2026高校电气电子工程创新大赛满足人数的记录。', '七名学生，未选择赛道，筛选2026高校电气电子工程创新大赛满足人数的记录。'],
     '自由命题最多5人、企业命题最多6人；未选择赛项时不能把不同上限合并为统一允许人数。', '自由命题'),
    ('2026091', 'test', 'historical', {'registration_status': 'open'},
     ['现在还能报2026米兰设计周高校展吗？只返回报名中赛事。', '今天想报名2026米兰设计周高校展，查仍开放的项目。'],
     '该届报名阶段为2025年10月至2026年3月，查询日2026-10-04已不在该阶段。', '2026年3月'),
    ('2026105', 'test', 'missing_data', {'team_size': 50},
     ['五十人学生队，筛出2026 FDI Moot符合人数上限的项目。', '查2026投资仲裁模拟赛能否确认容纳50名学生的一队。'],
     '现有正式知识未提供可核实的统一学生人数上限；不得把缺失人数规则视为允许50人。', '16000'),
    ('2026109', 'test', 'qualification_conflict', {'education': '博士'},
     ['博士研究生想报2025中国红十字国际人道法模拟法庭，筛出符合资格的记录。', '我在读博士，按2025中国人道法模拟法庭规则找能参赛的结果。'],
     '2025中国赛区规则排除博士研究生。', '博士'),
    ('2026155', 'test', 'hard_filter_conflict', {'team_size': 6},
     ['六名学生参加2025 IFLA学生竞赛，筛出符合人数的记录。', '查2025国际风景园林学生赛允许我们6人全员参赛的项目。'],
     '2025 IFLA允许个人或最多5人团队。', '5人'),
    ('2026248', 'test', 'hard_filter_conflict', {'team_size': 5},
     ['五名学生共同署名，筛选2026学院杯室内与环境设计大赛。', '查2026空间与情感主题比赛中能接受5名学生作者的记录。'],
     '2026学院杯学生作者不超过4人。', '作者≤4'),
]

# Positive boundary counterparts prevent an implementation that rejects every
# constrained request from passing. Each predicate comes from the cited rule.
CONSTRAINT_POSITIVES = {
    ('2026090', 1): ({'team_size': 2, 'education': '本科'}, '两名本科生组队参加2026诵读中国，查满足资格和人数的赛事。', '大学生组支持本科生，2人达到团队人数下限。'),
    ('2026090', 2): ({'team_size': 20, 'education': '本科'}, '二十名本科生组成一队，查2026诵读中国符合人数和学段的结果。', '大学生组支持本科生，20人达到团队人数上限。'),
    ('2026100', 1): ({'education': '本科', 'team_size': 3, 'participation_type': 'team'}, '三名本科生组队，查2026英特尔杯嵌入式系统专题赛符合条件的结果。', '普通高校全日制本科生每队3人，团队参赛。'),
    ('2026092', 1): ({'registration_status': 'open', 'education': '本科'}, '本科生查2026大广赛常规类别在2026年5月15日开放报名的记录。', '本科生属于参赛对象，2026-05-15位于常规类别报名提交窗口内。'),
    ('2026108', 1): ({'team_size': 3, 'participation_type': 'team'}, '三名学生组成口辩队，查2026 ICC模拟法庭符合学生人数的记录。', '每队3名口辩选手，可以不增加研究员，学生人数下限3人。'),
    ('2026113', 1): ({'team_size': 3, 'participation_type': 'team'}, '三名学生组队参加2026地质技能竞赛，查符合人数的结果。', '2026地质技能竞赛每队3人。'),
    ('2026115', 1): ({'team_size': 3, 'participation_type': 'team'}, '三名学生组队，查2026 CCE杯复合材料赛符合人数的结果。', '每队3—5名学生，3人达到学生人数下限；队伍中至少3人为本科生。'),
    ('2026143', 1): ({'participation_type': 'individual', 'edition': '2026年'}, '查2026届CCSP允许个人独立答题的项目。', '2026届CCSP是个人计算机系统与程序设计机试。'),
    ('2026148', 1): ({'team_size': 4, 'participation_type': 'team'}, '四名学生组成团队，查2026软件创新大赛符合人数的记录。', '学生队长1名和其他学生至多3名，4人符合上限。'),
    ('2026164', 1): ({'education': '本科', 'team_size': 5}, '五名本科生组队，查2026国地杯自然资源赛符合学段和人数的结果。', '面向全日制在校本专科生，学生最多5人。'),
}


def digest_bytes(value):
    return hashlib.sha256(value.replace(b'\r\n', b'\n')).hexdigest()


def catalog_codes(record):
    return set(record.get('catalog_codes') or [record.get('catalog_code')])


def normalize(text):
    return ''.join(str(text).split()).replace('—', '-').replace('–', '-').lower()


def bind_gold(corpus, code, anchor):
    year = HISTORICAL.get(code, '2026')
    candidates = [r for r in corpus['records'] if code in catalog_codes(r)
                  and (r.get('kind') == 'overview' or year in r.get('edition', ''))]
    bindings = []
    for record in candidates:
        sections = [s for s in record.get('sections', [])
                    if normalize(anchor) in normalize(s.get('text', ''))]
        if sections:
            bindings.append((record, sections))
    if not bindings:
        raise ValueError(f'Gold requires manual review: {code}, year={year}, anchor={anchor!r}')
    ids = sorted({r['id'] for r, _ in bindings})
    evidence_ids = sorted({eid for _, ss in bindings for s in ss for eid in s['evidence_ids']})
    references = []
    for record, sections in bindings:
        sources = {s['id']: s for s in record['sources']}
        for section in sections:
            references.append({'record_id': record['id'], 'section_id': section['id'],
                               'text': section['text'], 'evidence_ids': section['evidence_ids'],
                               'sources': [sources[eid] for eid in section['evidence_ids']]})
    return ids, evidence_ids, references


def build_cases(corpus, questions):
    cases = []
    for row in questions:
        code, split = row['code'], row['split']
        ids, evidence_ids, references = bind_gold(corpus, code, row['anchor'])
        for variant, key in enumerate(('query', 'semantic_query'), 1):
            filters, prefix = POSITIVE_FILTERS.get(code, ({}, ''))
            cases.append({'id': f'{split}-{code}-knowledge-{variant}', 'group': f'{code}-knowledge',
                          'split': split, 'scenario': ('multi_filter' if filters else 'exact') if variant == 1 else 'semantic',
                          'query': prefix + row[key], 'filters': filters, 'preferences': {}, 'as_of': '2026-10-04',
                          'relevant_ids': ids, 'evidence_ids': evidence_ids, 'expect_empty': False,
                          'catalog_codes': [code], 'gold_statement': row['gold_statement'],
                          'gold_references': references})
    for code, split, scenario, filters, queries, statement, anchor in CONSTRAINTS:
        ids, evidence_ids, references = bind_gold(corpus, code, anchor)
        for variant, query in enumerate(queries, 1):
            as_of = ['2026-05-15', '2026-10-04'][variant - 1] if scenario == 'time_boundary' else '2026-10-04'
            variant_filters, variant_statement = dict(filters), statement
            positive = CONSTRAINT_POSITIVES.get((code, variant))
            if positive:
                variant_filters, query, variant_statement = positive
            if code == '2026097' and variant == 2:
                variant_filters = {'team_size': 7}
            cases.append({'id': f'{split}-{code}-constraints-{variant}', 'group': f'{code}-constraints',
                          'split': split, 'scenario': 'multi_filter' if positive and scenario != 'time_boundary' else scenario,
                          'query': query, 'filters': {'catalog_codes': [code], **variant_filters}, 'preferences': {},
                          'as_of': as_of, 'relevant_ids': ids if positive else [], 'evidence_ids': evidence_ids,
                          'expect_empty': not bool(positive), 'catalog_codes': [code],
                          'gold_statement': variant_statement, 'gold_references': references})
    validate_cases(cases, corpus)
    return cases


def validate_cases(cases, corpus):
    if Counter(c['split'] for c in cases) != {'dev': 100, 'test': 50}:
        raise ValueError('Expected exactly 100 dev and 50 test cases')
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate case ids')
    for key in ('group', 'catalog_codes'):
        groups = {split: {g for c in cases if c['split'] == split
                          for g in (c[key] if isinstance(c[key], list) else [c[key]])}
                  for split in ('dev', 'test')}
        if groups['dev'] & groups['test']:
            raise ValueError(f'{key} overlap across dev/test')
    if len({code for c in cases for code in c['catalog_codes']}) < 50:
        raise ValueError('Fewer than 50 competition series')
    ids = {r['id'] for r in corpus['records']}
    evidence = {s['id'] for r in corpus['records'] for s in r['sources']}
    for case in cases:
        if not set(case['relevant_ids']) <= ids or not set(case['evidence_ids']) <= evidence:
            raise ValueError(f"Unknown gold identifier: {case['id']}")
        if bool(case['relevant_ids']) == case['expect_empty'] or not case['gold_references']:
            raise ValueError(f"Invalid gold case: {case['id']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=DEFAULT_CORPUS)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--check', action='store_true', help='Validate current fixtures without writing')
    parser.add_argument('--update-fixtures', action='store_true', help='Explicitly replace frozen fixtures after evidence review')
    args = parser.parse_args(argv)
    corpus = json.loads(args.corpus.read_text(encoding='utf-8-sig'))
    seed_path = DEFAULT_OUTPUT / 'questions.tsv'
    with seed_path.open(encoding='utf-8', newline='') as handle:
        questions = list(csv.DictReader(handle, delimiter='\t'))
    cases = build_cases(corpus, questions)
    outputs = {f'{split}.jsonl': ''.join(json.dumps(c, ensure_ascii=False, sort_keys=True) + '\n'
                                        for c in cases if c['split'] == split).encode('utf-8')
               for split in ('dev', 'test')}
    manifest = {'schema_version': 1, 'corpus_version': corpus['version'],
                'questions_sha256': digest_bytes(seed_path.read_bytes()),
                'files': {name: {'sha256': digest_bytes(data), 'count': 100 if name.startswith('dev') else 50}
                          for name, data in outputs.items()},
                'series_count': len({code for c in cases for code in c['catalog_codes']}),
                'scenarios': dict(Counter(c['scenario'] for c in cases)),
                'gold_origin': 'Independently authored from source facts; search is never called during fixture creation.',
                'frozen_test_policy': 'Test is for final reporting. Calibration uses dev only; fixture edits require evidence review.'}
    outputs['manifest.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if args.check:
        for name, data in outputs.items():
            if not (args.output / name).exists() or (args.output / name).read_bytes().replace(b'\r\n', b'\n') != data:
                raise ValueError(f'Fixture differs: {name}')
    else:
        if not args.update_fixtures and any((args.output / name).exists() for name in outputs):
            raise ValueError('Fixtures are frozen; use --check or explicitly --update-fixtures after evidence review')
        args.output.mkdir(parents=True, exist_ok=True)
        for name, data in outputs.items():
            (args.output / name).write_bytes(data)
    print(json.dumps({'cases': len(cases), 'series': manifest['series_count'], 'corpus_version': corpus['version']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
