"""Offline behavioral checks, also runnable with python -m unittest without Django."""

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from .competition_search import database_corpus, interpret_query, search_competitions
from .semantic import LocalBGEEncoder, SemanticError, build_index, load_index, save_index


def record(identifier='robot', *, competition_id=7, **changes):
    fields = {
        'eligibility': '本科生大二及以上，专业不限，团队参赛，每队 2—5 人。',
        'education': ['本科生'], 'grades': ['大二及以上'], 'majors': ['不限专业'],
        'participation_type': 'team', 'team_size_min': 2, 'team_size_max': 5,
        'registration_start': '2026-09-01', 'registration_deadline': '2026-10-31',
        'submission_deadline': '2026-12-01', 'registration_url': 'https://robot.example.edu/register',
    }
    source = {'id': f'{identifier}-rules', 'url': 'https://robot.example.edu/rules',
              'title': '机器人设计挑战赛规则', 'quote': '本科生大二及以上，每队 2—5 人，报名时间为 2026 年 9 月 1 日至 10 月 31 日。',
              'locator': '参赛规则第 2 条', 'verified_at': '2026-10-01'}
    result = {
        'id': identifier, 'catalog_code': '2026001', 'competition_id': competition_id,
        'code': f'{identifier}-2026', 'title': '机器人设计挑战赛', 'edition': '2026',
        'category': {'code': 'engineering', 'name': '工程技术'}, 'level': 'national',
        'aliases': ['机器人挑战赛', 'RDC'], 'summary': '设计能够自主导航的机器人系统。',
        'fields': fields, 'field_evidence': {key: [source['id']] for key in fields},
        'sources': [source], 'sections': [{'id': identifier + '-eligibility', 'heading': '参赛资格',
                                         'text': fields['eligibility'] + '机器人设计与自主导航。',
                                         'evidence_ids': [source['id']]}],
        'content_hash': 'hash-' + identifier, 'review_status': 'approved', 'publication_status': 'published',
    }
    result.update(changes)
    return result


def corpus(*rows):
    return {'schema_version': 1, 'version': 'fixture-v1', 'as_of': '2026-10-04', 'records': list(rows or [record()])}


def search(query='机器人', **kwargs):
    return search_competitions(query, corpus=kwargs.pop('corpus', corpus()), as_of='2026-10-04',
                               mode=kwargs.pop('mode', 'keyword'), **kwargs)


class CompetitionSearchTests(unittest.TestCase):
    def test_exact_alias_precedes_loose_title_match(self):
        other = record('other', title='RDC 算法学习交流赛', aliases=[], competition_id=9)
        response = search('ＲＤＣ', corpus=corpus(other, record()))
        self.assertEqual(response['hits'][0]['record_id'], 'robot')
        self.assertEqual(response['mode_used'], 'keyword')

    def test_chinese_without_spaces_and_topic_aliases(self):
        self.assertEqual(search('想找适合我的机器人比赛')['hits'][0]['record_id'], 'robot')
        ai = record(title='智能算法挑战赛', aliases=[], summary='使用机器学习开展人工智能研究。')
        self.assertTrue(search('AI 相关', corpus=corpus(ai))['hits'])
        self.assertEqual(search('天文考古比赛')['hits'], [])

    def test_ascii_word_boundaries_and_modeling_topics(self):
        row = record(title='RAICOM 制造竞赛', aliases=[], summary='Daily training', sections=[])
        self.assertEqual(search('AI相关', corpus=corpus(row))['hits'], [])
        architecture = record(title='建筑模型挑战赛', aliases=[], summary='建筑三维建模。', sections=[])
        self.assertEqual(search('数学建模', corpus=corpus(architecture))['hits'], [])
        architecture['summary'] = '提交 STL 数模与三维模型。'
        self.assertEqual(search('数学建模', corpus=corpus(architecture))['hits'], [])
        court = record(title='国际模拟法庭', aliases=['ICC'], summary='三方书状须匿名，AI使用另查Art30。', sections=[])
        self.assertEqual(search('AI相关', corpus=corpus(court))['hits'], [])
        self.assertTrue(search('ICC的AI使用规则', corpus=corpus(court))['hits'])

    def test_profile_is_preference_and_grade_range_is_not_exact_text(self):
        interpretation, hard, preferred = interpret_query('我是大二物理专业学生，喜欢机器人')
        self.assertEqual(interpretation['major'], '物理')
        self.assertEqual(hard, {})
        self.assertEqual(preferred['grade'], '大二')
        self.assertTrue(search(filters={'grade': '大三'})['hits'])
        self.assertFalse(search(filters={'grade': '大一'})['hits'])
        self.assertNotIn('participation_type', interpret_query('必须数学相关，最好个人参加')[1])
        self.assertEqual(interpret_query('只找支持个人参加的数学比赛')[1]['participation_type'], 'individual')

    def test_long_request_needs_substantial_lexical_topic_overlap(self):
        unrelated = record(title='职业规划大赛', aliases=[], summary='介绍年龄分组、报名安排及职业规划。', sections=[])
        self.assertFalse(search('我要了解职业潜水资格认证，需要水下减压训练、潜伴救援和开放水域考核。',
                                corpus=corpus(unrelated))['hits'])
        self.assertFalse(search('想找按年龄分组的越野滑雪活动，要求林间雪道、计时冲刺和交替滑行。',
                                corpus=corpus(unrelated))['hits'])
        # A specific title phrase or several shared task terms still works.
        self.assertTrue(search('想了解职业规划大赛的报名材料以及全国选拔安排。', corpus=corpus(unrelated))['hits'])
        matching = record(title='水质分析赛', aliases=[], summary='检测水样中的化学需氧量、氨氮与大肠菌群。', sections=[])
        self.assertTrue(search('我在做水质污染检测，希望任务涉及化学需氧量、氨氮分析和大肠菌群。',
                               corpus=corpus(matching))['hits'])

    def test_unknown_does_not_satisfy_hard_qualification(self):
        row = record()
        row['fields']['grades'] = []
        self.assertEqual(search(corpus=corpus(row), filters={'grade': '大二'})['hits'], [])
        self.assertTrue(search(corpus=corpus(row), preferences={'grade': '大二'})['hits'])
        reasons = search(corpus=corpus(row), preferences={'grade': '大二'})['hits'][0]['match_reasons']
        self.assertFalse(any('年级' in item['text'] for item in reasons))
        checks = search(corpus=corpus(row), preferences={'grade': '大二'})['hits'][0]['condition_checks']
        self.assertEqual(checks, [{'field': 'grade', 'role': 'preference', 'value': '大二', 'state': 'unknown'}])

    def test_unsubstantiated_fields_do_not_satisfy_hard_filters(self):
        for name, field in (('grade', 'grades'), ('team_size', 'team_size_min'), ('registration_status', 'registration_start')):
            row = record()
            row['field_evidence'][field] = ['missing-source']
            value = {'grade': '大二', 'team_size': 3, 'registration_status': 'open'}[name]
            with self.subTest(field=field):
                self.assertFalse(search(corpus=corpus(row), filters={name: value})['hits'])

    def test_major_unrestricted_and_education_levels(self):
        self.assertTrue(search(filters={'major': '物理', 'education': 'undergraduate'})['hits'])
        self.assertFalse(search(filters={'education': 'master'})['hits'])

    def test_team_size_and_participation_are_independent(self):
        self.assertTrue(search(filters={'team_size': 5, 'participation_type': 'team'})['hits'])
        self.assertFalse(search(filters={'team_size': 6})['hits'])
        self.assertFalse(search(filters={'participation_type': 'individual'})['hits'])
        row = record()
        row['fields']['team_size_max'] = None
        self.assertFalse(search(corpus=corpus(row), filters={'team_size': 3})['hits'])

    def test_deadline_alone_never_means_registration_open(self):
        row = record()
        row['fields']['registration_start'] = None
        self.assertFalse(search('机器人还能报名吗', corpus=corpus(row))['hits'])
        self.assertTrue(search('机器人还能报名吗')['hits'])
        row['fields']['registration_deadline'] = None
        self.assertFalse(search('机器人可报名', corpus=corpus(row))['hits'])

    def test_submission_deadline_does_not_extend_registration(self):
        row = record()
        row['fields']['registration_deadline'] = '2026-09-30'
        self.assertFalse(search('机器人可报名', corpus=corpus(row))['hits'])
        self.assertTrue(search(corpus=corpus(row), filters={'registration_status': 'closed'})['hits'])

    def test_official_registration_status_needs_current_date_and_both_evidence_refs(self):
        for status in ('open', 'closed', 'upcoming'):
            row = record()
            row['fields'].update(registration_start=None, registration_deadline=None,
                                 registration_status=status, status_as_of='2026-10-04')
            row['field_evidence'].update(registration_status=['robot-rules'], status_as_of=['robot-rules'])
            with self.subTest(status=status):
                self.assertTrue(search(corpus=corpus(row), filters={'registration_status': status})['hits'])
                row['fields']['status_as_of'] = '2026-10-03'
                self.assertFalse(search(corpus=corpus(row), filters={'registration_status': status})['hits'])
                row['fields']['status_as_of'] = '2026-10-04'
                row['field_evidence']['status_as_of'] = []
                self.assertFalse(search(corpus=corpus(row), filters={'registration_status': status})['hits'])

    def test_inclusive_deadline_date_and_future_start(self):
        row = record()
        row['fields']['registration_deadline'] = '2026-10-04'
        self.assertTrue(search(corpus=corpus(row), filters={'registration_status': 'open'})['hits'])
        row['fields']['registration_start'] = '2026-10-05'
        row['fields']['registration_deadline'] = '2026-10-31'
        self.assertTrue(search(corpus=corpus(row), filters={'registration_status': 'upcoming'})['hits'])

    def test_filter_only_query_and_catalog_scope(self):
        self.assertTrue(search('', filters={'catalog_codes': ['2026001'], 'deadline_to': '2026-11-01'})['hits'])
        self.assertFalse(search('', filters={'catalog_codes': ['2026999']})['hits'])
        reused = record(catalog_codes=['2026001', '2026099'])
        self.assertTrue(search('', corpus=corpus(reused), filters={'catalog_codes': ['2026099']})['hits'])

    def test_unapproved_withdrawn_or_sourceless_documents_never_return(self):
        for change in ({'review_status': 'draft'}, {'publication_status': 'withdrawn'}, {'sources': []}):
            with self.subTest(change=change):
                self.assertEqual(search(corpus=corpus(record(**change)))['hits'], [])

    def test_real_ids_only_in_card_results_and_common_hits(self):
        data = corpus(record('robot', competition_id=None), record('public', competition_id=15))
        response = search(corpus=data)
        self.assertEqual(len(response['hits']), 2)
        self.assertEqual(response['results'][0]['competition']['id'], 15)
        self.assertEqual(response['knowledge_results'][0]['record_id'], 'robot')
        for bad_id in (True, 0, -7, '42', 9007199254740992):
            self.assertEqual(search(corpus=corpus(record(competition_id=bad_id)))['results'], [])

    def test_multiple_documents_for_one_competition_produce_one_card(self):
        response = search(corpus=corpus(record('document-one'), record('document-two')))
        self.assertEqual(len(response['hits']), 2)
        self.assertEqual(len(response['results']), 1)
        self.assertEqual(response['results'][0]['competition']['id'], 7)
        self.assertEqual(response['knowledge_results'], [])

    def test_unknown_card_values_are_neutral(self):
        row = record(category='')
        row['fields'].update(registration_start=None, registration_deadline=None, submission_deadline=None)
        card = search(corpus=corpus(row))['results'][0]['competition']
        self.assertIsNone(card['category'])
        self.assertEqual(card['deadline_status_label'], '报名时间信息不足')

    def test_fact_reasons_have_traceable_evidence_and_no_internal_keys(self):
        row = record()
        row['internal_review'] = 'not-public'
        row['sources'][0]['raw_path'] = 'private.txt'
        row['fields']['reviewer'] = 'private-reviewer'
        row['category']['audit_notes'] = 'private-category'
        response = search(corpus=corpus(row), filters={'team_size': 3})
        hit = response['hits'][0]
        ids = {item['id'] for item in hit['evidence']}
        self.assertTrue(all(set(reason['evidence_ids']) <= ids for reason in hit['match_reasons']))
        serialized = json.dumps(response)
        for secret in ('not-public', 'private.txt', 'private-reviewer', 'private-category'):
            self.assertNotIn(secret, serialized)
        self.assertIn('符合 3 人组队需求', response['results'][0]['matchReason'])
        self.assertEqual(hit['content_hash'], row['content_hash'])
        self.assertEqual(hit['passages'][0]['text'], row['sections'][0]['text'])
        self.assertEqual(response['results'][0]['passages'], hit['passages'])
        self.assertTrue(all(set(passage['evidence_ids']) <= ids for passage in hit['passages']))

    def test_input_validation(self):
        for options in ({'limit': True}, {'mode': 'fake'}, {'mode': []}, {'filters': {'unknown': 'x'}},
                        {'filters': {'team_size': 0}}, {'filters': {'education': 'banana'}},
                        {'filters': {'grade': '随意一年'}}, {'filters': {'level': 'banana'}},
                        {'filters': {'deadline_from': '2026-11-01', 'deadline_to': '2026-10-01'}}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                search(**options)
        with self.assertRaises(ValueError):
            search('x' * 501)
        with self.assertRaises(ValueError):
            search('')

    def test_invalid_corpus_types_enums_dates_and_ranges_are_rejected(self):
        for change in ({'level': []}, {'sources': 'bad'}, {'sections': 'bad'}, {'review_status': 'typo'},
                       {'publication_status': 'typo'}, {'aliases': 'RDC'}, {'summary': {'private': 'x'}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                search(corpus=corpus(record(**change)))
        for field, value in [('grades', '大二'), ('team_size_min', True), ('team_size_min', 10),
                             ('participation_type', 'squad'), ('registration_deadline', '2026-02-30')]:
            row = record()
            row['fields'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                search(corpus=corpus(row))

    def test_empty_result_distinguishes_conflict_and_unknown(self):
        unknown = record('unknown')
        unknown['fields']['team_size_min'] = None
        response = search(corpus=corpus(record(), unknown), filters={'team_size': 6})
        empty = response['empty_result']
        self.assertEqual(empty['code'], 'no_condition_match')
        self.assertIn('团队人数：6', empty['message'])
        self.assertEqual({key: empty['conditions'][0][key] for key in ('matched', 'unmatched', 'unknown')},
                         {'matched': 0, 'unmatched': 1, 'unknown': 1})
        self.assertEqual(search('天文考古')['empty_result']['code'], 'no_topic_match')
        self.assertEqual(search(corpus={'schema_version': 1, 'version': 'empty', 'records': []})['empty_result']['code'], 'empty_corpus')

    def test_registration_conflict_can_be_known_without_start_date(self):
        row = record()
        row['fields']['registration_start'] = None
        row['fields']['registration_deadline'] = '2026-09-01'
        state = search(corpus=corpus(row), filters={'registration_status': 'open'})['empty_result']['conditions'][0]
        self.assertEqual(state['unmatched'], 1)
        self.assertEqual(state['unknown'], 0)

    def test_missing_index_reports_keyword_fallback(self):
        with patch.dict(os.environ, {'COMPETITION_SEMANTIC_INDEX': ''}):
            response = search(mode='hybrid')
        self.assertEqual(response['mode_used'], 'keyword')
        self.assertEqual(response['warnings'][0]['code'], 'semantic_index_unconfigured')
        self.assertTrue(response['hits'])

    def test_model_input_is_not_silently_truncated(self):
        encoder = object.__new__(LocalBGEEncoder)
        encoder.model = MagicMock()
        encoder.model.max_seq_length = 4
        encoder.model.tokenizer.return_value = {'input_ids': [[1, 2, 3, 4, 5]]}
        with self.assertRaisesRegex(SemanticError, 'semantic_query_too_long'):
            encoder.encode(['这是很长的需求'], is_query=True)
        encoder.model.encode.assert_not_called()

    def test_duplicate_record_id_is_rejected(self):
        with self.assertRaises(ValueError):
            search(corpus=corpus(record(), record()))

    def test_default_database_adapter_uses_real_link_and_serializer(self):
        row = record(competition_id=None)
        link = SimpleNamespace(competition_id=42, competition=SimpleNamespace(publication_status='published'))
        links = MagicMock()
        links.all.return_value = [link]
        body = '\n\n'.join(f"## {section['heading']}\n\n{section['text']}" for section in row['sections'])
        revision = SimpleNamespace(metadata={'search_record': row}, content_hash='document-hash', links=links,
                                   body=body, title=row['title'], edition=row['edition'], sources=deepcopy(row['sources']), version=1)
        document = SimpleNamespace(current_revision=revision, review_status='approved', code='final-robot')
        documents = MagicMock()
        documents.select_related.return_value.prefetch_related.return_value = [document]
        public_object = SimpleNamespace(pk=42)
        public_mixin = MagicMock()
        public_mixin.return_value.get_queryset.return_value.filter.return_value = [public_object]
        serialized = {'id': 42, 'title': row['title'], 'code': row['code'], 'category': row['category'],
                      'tags': [], 'private_field': 'internal-value'}
        serializer = MagicMock(return_value=SimpleNamespace(data=serialized))
        modules = {
            'curation.retrieval': SimpleNamespace(student_visible_documents=lambda: documents),
            'competitions.views': SimpleNamespace(PublicCompetitionMixin=public_mixin),
            'competitions.serializers': SimpleNamespace(CompetitionListSerializer=serializer),
        }
        with patch.dict(sys.modules, modules):
            response = search_competitions('机器人', as_of='2026-10-04', mode='keyword')
        self.assertEqual(response['results'][0]['competition']['id'], 42)
        self.assertNotIn('internal-value', json.dumps(response))
        serializer.assert_called_once_with(public_object)
        self.assertIsNone(row['competition_id'])
        with patch.dict(sys.modules, modules):
            original_version = database_corpus()['version']
            revision.version = 2
            self.assertNotEqual(database_corpus()['version'], original_version)
            revision.body += '\n已改正文'
            changed = database_corpus()
            self.assertEqual(changed['records'], [])
            self.assertEqual(changed['diagnostics'][0]['code'], 'document_search_record_mismatch')
            self.assertEqual(search_competitions('机器人', as_of='2026-10-04', mode='keyword')['hits'], [])
            revision.body = body
            revision.sources[0]['url'] = 'https://changed.example.edu/new-rules'
            self.assertEqual(database_corpus()['records'], [])


class ToyEncoder:
    model_id = 'unit-test-encoder'
    revision = 'test-revision'

    def encode(self, texts, *, is_query=False):
        return [[1, 0, 0] if ('机器人' in text or '自动机械装置' in text) else [0, 1, 0]
                for text in texts]


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'NumPy is installed in the retrieval environment')
class SemanticSearchTests(unittest.TestCase):
    def setUp(self):
        self.corpus = corpus()
        self.index = build_index(self.corpus, encoder=ToyEncoder())

    def test_paraphrase_is_found_semantically(self):
        self.assertEqual(search('自动机械装置', corpus=self.corpus)['hits'], [])
        response = search('自动机械装置', corpus=self.corpus, index=self.index, mode='semantic')
        self.assertEqual(response['hits'][0]['record_id'], 'robot')
        self.assertEqual(response['mode_used'], 'semantic')
        self.assertEqual(response['warnings'], [])

    def test_hybrid_merges_same_record_and_preserves_hard_filters(self):
        response = search(corpus=self.corpus, index=self.index, mode='hybrid')
        self.assertEqual(len(response['hits']), 1)
        self.assertAlmostEqual(response['hits'][0]['score'], 2 / 61)
        response = search(corpus=self.corpus, index=self.index, mode='hybrid', filters={'team_size': 9})
        self.assertEqual(response['hits'], [])

    def test_low_similarity_has_no_semantic_hit(self):
        self.assertEqual(search('商业计划', corpus=self.corpus, index=self.index, mode='semantic')['hits'], [])

    def test_topic_reason_uses_topic_source_when_semantic_passage_differs(self):
        row = record(title='智能系统挑战赛', aliases=[], summary='自主导航与AI研究。')
        row['sources'].append({**row['sources'][0], 'id': 'ai-rules', 'title': 'AI赛道规则'})
        row['sections'].append({'id': 'ai-track', 'heading': 'AI赛道', 'text': '通过AI技术完成图像分析。',
                                'evidence_ids': ['ai-rules']})
        data = corpus(row)
        index = build_index(data, encoder=ToyEncoder())
        hit = search('自动机械装置AI研究', corpus=data, index=index, mode='hybrid')['hits'][0]
        topic_reason = next(item for item in hit['match_reasons'] if '赛事内容涉及' in item['text'])
        self.assertEqual(topic_reason['evidence_ids'], ['ai-rules'])
        self.assertEqual(hit['passages'][0]['id'], 'robot-eligibility')

    def test_stale_content_and_withdrawal_trigger_diagnosable_fallback(self):
        for change in ({'content_hash': 'updated'}, {'publication_status': 'withdrawn'}):
            changed = deepcopy(self.corpus)
            changed['records'][0].update(change)
            response = search(corpus=changed, index=self.index, mode='hybrid')
            self.assertEqual(response['mode_used'], 'keyword')
            self.assertEqual(response['warnings'][0]['code'], 'semantic_index_stale')
            if 'publication_status' in change:
                self.assertEqual(response['hits'], [])

    def test_changed_payload_with_unchanged_hash_invalidates_index(self):
        changed = deepcopy(self.corpus)
        changed['records'][0]['sections'][0]['text'] = '本届仅限化学实验。'
        response = search('自动机械装置', corpus=changed, index=self.index, mode='hybrid')
        self.assertEqual(response['mode_used'], 'keyword')
        self.assertEqual(response['warnings'][0]['code'], 'semantic_index_stale')
        self.assertEqual(response['hits'], [])
        # A database link does not rewrite the imported knowledge content.
        linked = deepcopy(self.corpus)
        linked['records'][0]['competition_id'] = 99
        self.assertEqual(search(corpus=linked, index=self.index, mode='semantic')['mode_used'], 'semantic')

    def test_npz_round_trip_and_damaged_index(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'index.npz'
            save_index(self.index, path)
            loaded = load_index(path, encoder=ToyEncoder())
            self.assertEqual(search(corpus=self.corpus, index=loaded, mode='semantic')['mode_used'], 'semantic')
            path.write_bytes(b'not an index')
            response = search(corpus=self.corpus, index=path, mode='semantic')
            self.assertEqual(response['mode_used'], 'keyword')
            self.assertEqual(response['warnings'][0]['code'], 'semantic_index_unreadable')
            path.write_bytes(b'')
            response = search(corpus=self.corpus, index=path, mode='semantic')
            self.assertEqual(response['mode_used'], 'keyword')
            self.assertEqual(response['warnings'][0]['code'], 'semantic_index_unreadable')

    def test_model_revision_mismatch_is_rejected(self):
        self.index.metadata['model_revision'] = 'other-revision'
        with self.assertRaisesRegex(SemanticError, 'semantic_model_mismatch'):
            self.index.validate(self.corpus)

    def test_unknown_evidence_and_wrong_vector_shape_are_rejected(self):
        self.index.metadata['chunks'][0]['evidence_ids'] = ['unrelated-source']
        with self.assertRaisesRegex(SemanticError, 'semantic_evidence_invalid'):
            self.index.validate(self.corpus)
        self.index.metadata['chunks'][0]['evidence_ids'] = ['robot-rules']
        self.index.vectors = [[float('nan'), 0, 1]]
        with self.assertRaisesRegex(SemanticError, 'embedding_shape_invalid'):
            self.index.validate(self.corpus)

    def test_invalid_chunk_schema_and_missing_sections_are_rejected(self):
        self.index.metadata['chunks'][0]['section_id'] = 'absent-section'
        with self.assertRaisesRegex(SemanticError, 'semantic_section_invalid'):
            self.index.validate(self.corpus)
        self.index.metadata['chunks'][0] = 'bad-chunk'
        with self.assertRaisesRegex(SemanticError, 'semantic_chunk_invalid'):
            self.index.validate(self.corpus)

    def test_corpus_version_change_alone_invalidates_index(self):
        revised = deepcopy(self.corpus)
        revised['version'] = 'new-document-revision'
        response = search(corpus=revised, index=self.index, mode='hybrid')
        self.assertEqual(response['mode_used'], 'keyword')
        self.assertEqual(response['warnings'][0]['code'], 'semantic_index_stale')


if __name__ == '__main__':
    unittest.main()
