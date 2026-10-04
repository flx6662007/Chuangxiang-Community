"""Regression tests for evaluation integrity, independent of retrieval and models."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


evaluation = module('competition_evaluation', 'evaluate-competition-search.py')
builder = module('competition_fixture_builder', 'build-competition-evaluation.py')


class EvaluationIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.record = {'id': 'r1', 'catalog_codes': ['2026001'], 'fields': {'team_size_min': 2, 'team_size_max': 4},
                       'field_evidence': {'team_size_min': ['e1'], 'team_size_max': ['e1']},
                       'sources': [{'id': 'e1', 'url': 'https://example.org/rules', 'locator': '规则第2条', 'verified_at': '2026-10-04'}],
                       'review_status': 'approved', 'publication_status': 'published'}
        self.corpus = {'version': 'v1', 'records': [self.record]}
        self.case = {'id': 'case1', 'group': 'group1', 'scenario': 'semantic', 'query': '搭建竞赛原型',
                     'filters': {}, 'preferences': {}, 'as_of': '2026-10-04',
                     'relevant_ids': ['r1'], 'evidence_ids': ['e1'], 'expect_empty': False}

    def test_missing_model_cannot_pass_empty_question(self):
        case = {**self.case, 'expect_empty': True, 'relevant_ids': []}
        def broken(*args, **kwargs):
            raise RuntimeError('embedding_model_unavailable')
        result = evaluation.run_mode([case], self.corpus, broken, 'semantic')
        self.assertEqual(result['metrics']['empty_accuracy'], 0)
        self.assertEqual(result['metrics']['operational_errors'], 1)
        self.assertFalse(result['metrics']['passes_targets'])

    def test_hybrid_degradation_is_not_a_successful_semantic_measurement(self):
        result = evaluation.run_mode([self.case], self.corpus,
                                     lambda *a, **kw: {'hits': [], 'warnings': ['model_unavailable']}, 'hybrid')
        self.assertEqual(result['metrics']['operational_errors'], 1)

    def test_missing_hits_is_not_a_correct_empty_result(self):
        case = {**self.case, 'expect_empty': True, 'relevant_ids': []}
        result = evaluation.run_mode([case], self.corpus, lambda *a, **kw: {'error': 'invalid'}, 'keyword')
        self.assertEqual(result['metrics']['operational_errors'], 1)
        self.assertEqual(result['metrics']['empty_accuracy'], 0)

    def test_unknown_or_unproven_team_bounds_are_violations(self):
        self.assertEqual(evaluation.hard_violations(self.record, {'team_size': 3}, '2026-10-04'), [])
        self.assertEqual(evaluation.hard_violations(self.record, {'team_size': 5}, '2026-10-04'), ['team_size'])
        self.record['field_evidence'] = {}
        self.assertEqual(evaluation.hard_violations(self.record, {'team_size': 3}, '2026-10-04'), ['team_size'])
        self.record['field_evidence'] = {'team_size_min': ['invented'], 'team_size_max': ['invented']}
        self.assertEqual(evaluation.hard_violations(self.record, {'team_size': 3}, '2026-10-04'), ['team_size'])

    def test_registration_deadline_without_start_does_not_prove_open(self):
        self.record['fields'] = {'registration_deadline': '2026-10-10'}
        self.record['field_evidence'] = {'registration_deadline': ['e1']}
        self.assertEqual(evaluation.hard_violations(self.record, {'registration_status': 'open'}, '2026-10-04'), ['registration_status'])

    def test_exact_registration_boundaries_are_inclusive(self):
        self.record['fields'] = {'registration_start': '2026-10-01', 'registration_deadline': '2026-10-10'}
        self.record['field_evidence'] = {'registration_start': ['e1'], 'registration_deadline': ['e1']}
        for current in ('2026-10-01', '2026-10-10'):
            self.assertEqual(evaluation.hard_violations(self.record, {'registration_status': 'open'}, current), [])
        for current in ('2026-09-30', '2026-10-11'):
            self.assertEqual(evaluation.hard_violations(self.record, {'registration_status': 'open'}, current), ['registration_status'])

    def test_dated_official_status_is_limited_to_its_stated_day(self):
        self.record['fields'] = {'registration_status': 'open', 'status_as_of': '2026-10-04'}
        self.record['field_evidence'] = {'registration_status': ['e1'], 'status_as_of': ['e1']}
        self.assertEqual(evaluation.hard_violations(self.record, {'registration_status': 'open'}, '2026-10-04'), [])
        self.assertEqual(evaluation.hard_violations(self.record, {'registration_status': 'open'}, '2026-10-05'), ['registration_status'])
        self.record['fields']['registration_deadline'] = '2026-10-03'
        self.record['field_evidence']['registration_deadline'] = ['e1']
        self.assertEqual(evaluation.hard_violations(self.record, {'registration_status': 'open'}, '2026-10-04'), ['registration_status'])

    def test_unreturned_or_invented_citation_is_not_grounded(self):
        hit = {'record_id': 'r1', 'evidence': [{'id': 'fake'}],
               'match_reasons': [{'text': '适合学生', 'evidence_ids': ['e1']}]}
        result = evaluation.evaluate_case(self.case, {'hits': [hit]}, self.corpus)
        self.assertTrue(result['hit_at_5'])
        self.assertFalse(result['gold_evidence_hit'])
        self.assertEqual(result['grounded_reason_count'], 0)
        self.assertEqual(result['unresolved_evidence_ids'], ['fake'])

    def test_relevant_hit_outside_first_five_does_not_count(self):
        result = evaluation.evaluate_case(self.case, {'hits': [{'record_id': f'other-{i}'} for i in range(5)] + [{'record_id': 'r1'}]}, self.corpus)
        self.assertFalse(result['hit_at_5'])

    def test_withdrawn_result_is_a_violation(self):
        self.record['publication_status'] = 'withdrawn'
        result = evaluation.evaluate_case(self.case, {'hits': [{'record_id': 'r1'}]}, self.corpus)
        self.assertEqual(result['hard_violations'][0]['filters'], ['visibility'])

    def test_returning_no_reasons_cannot_claim_complete_evidence_coverage(self):
        result = evaluation.evaluate_case(self.case, {'hits': [{'record_id': 'r1'}]}, self.corpus)
        metrics = evaluation.summarize([result])
        self.assertEqual(metrics['hits_without_reason'], 1)
        self.assertFalse(metrics['passes_targets'])

    def test_operational_failure_stays_in_hit_denominator(self):
        details = [{'expect_empty': False, 'scenario': 'semantic', 'hit_at_5': True},
                   {'expect_empty': False, 'scenario': 'semantic', 'error': 'broken', 'hit_at_5': False}]
        metrics = evaluation.summarize(details)
        self.assertEqual(metrics['hit_at_5'], .5)
        self.assertEqual(metrics['semantic_hit_at_5'], .5)

    def test_empty_only_probe_reports_are_usable(self):
        details = [{'expect_empty': True, 'scenario': 'no_topic_match', 'empty_correct': True,
                    'empty_explanation_valid': True}]
        metrics = evaluation.summarize(details)
        self.assertIsNone(metrics['hit_at_5'])
        self.assertEqual(metrics['empty_accuracy'], 1)
        self.assertTrue(metrics['passes_targets'])

    def test_empty_result_requires_an_explanation_and_explicit_conditions(self):
        case = {**self.case, 'expect_empty': True, 'relevant_ids': [], 'filters': {'team_size': 5}}
        detail = evaluation.evaluate_case(case, {'hits': []}, self.corpus)
        self.assertTrue(detail['empty_correct'])
        self.assertFalse(evaluation.summarize([detail])['passes_targets'])
        response = {'hits': [], 'empty_result': {'code': 'no_condition_match',
                    'message': '没有同时满足人数为5的赛事。', 'conditions': []}}
        self.assertFalse(evaluation.evaluate_case(case, response, self.corpus)['empty_explanation_valid'])
        response['empty_result']['conditions'] = [{'field': 'team_size', 'value': 5}]
        self.assertTrue(evaluation.evaluate_case(case, response, self.corpus)['empty_explanation_valid'])

    def test_small_probe_p95_does_not_hide_the_slow_request(self):
        self.assertEqual(evaluation.percentile([10, 5000], .95), 5000)

    def test_fixed_case_counts_and_disjoint_series(self):
        with (ROOT / 'docs/competition-evaluation/questions.tsv').open(encoding='utf-8', newline='') as handle:
            rows = list(csv.DictReader(handle, delimiter='\t'))
        self.assertEqual(len(rows), 60)
        self.assertEqual(len({r['code'] for r in rows}), 60)
        self.assertEqual(sum(r['split'] == 'dev' for r in rows), 40)
        self.assertEqual(sum(r['split'] == 'test' for r in rows), 20)
        split_by_code = {r['code']: r['split'] for r in rows}
        for code, split, *_ in builder.CONSTRAINTS:
            self.assertEqual(split_by_code[code], split)
        self.assertEqual(sum(c[1] == 'dev' for c in builder.CONSTRAINTS), 10)
        self.assertEqual(sum(c[1] == 'test' for c in builder.CONSTRAINTS), 5)
        self.assertGreaterEqual(len(builder.CONSTRAINT_POSITIVES), 10)

    def test_tampered_fixture_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            data = (json.dumps(self.case) + '\n').encode('utf-8')
            manifest = {'corpus_version': 'v1', 'files': {'dev.jsonl': {'sha256': hashlib.sha256(data).hexdigest(), 'count': 1}}}
            (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            (directory / 'dev.jsonl').write_bytes(data)
            self.assertEqual(len(evaluation.load_fixture(directory, 'dev', self.corpus)), 1)
            (directory / 'dev.jsonl').write_bytes(data.replace(b'\n', b'\r\n'))
            self.assertEqual(len(evaluation.load_fixture(directory, 'dev', self.corpus)), 1)
            (directory / 'dev.jsonl').write_bytes(data + b'\n')
            with self.assertRaisesRegex(ValueError, 'fixture_hash_mismatch'):
                evaluation.load_fixture(directory, 'dev', self.corpus)


if __name__ == '__main__':
    unittest.main()
