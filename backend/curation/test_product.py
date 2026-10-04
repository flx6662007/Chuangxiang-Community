"""Evidence and content regression checks, independent of Django/database."""
import unittest

from curation.product import (build_edition_record, build_overview_record,
                              clean_text, fact_fields, supported_fields, education_from_eligibility,
                              add_discovery_metadata)
from curation.product import add_explicit_study_filters, source_record, prepare_resource, product_title


SOURCE = {'id': 's1', 'url': 'https://example.org/rules', 'title': '2026竞赛规则',
          'checked_on': '2026-10-03', 'locator': '参赛对象'}


class ProductTests(unittest.TestCase):
    def test_catalog_year_removed_when_ordinal_edition_has_only_id_year(self):
        self.assertEqual(product_title('全国大学生海洋知识竞赛（2026）', '第十四届',
                                      'curated-c114-2024-2'), '全国大学生海洋知识竞赛')

    def test_explicit_edition_year_takes_precedence_and_hash_is_not_a_year(self):
        self.assertEqual(product_title('比赛（2026）', '2025年', 'curated-c123-2026-1'), '比赛')
        self.assertEqual(product_title('比赛（2026）', '第十四届', 'curated-c123-2024abcd'), '比赛（2026）')

    def test_search_snippet_without_readable_body_is_not_evidence(self):
        self.assertIsNone(source_record(SOURCE, '搜索可读取的2026系列页；直接页面正文空'))

    def test_explicit_major_and_grade_share_the_eligibility_evidence(self):
        fields = {'eligibility': '德语专业本科生，年级不限。'}
        evidence = {'eligibility': ['source-eligibility']}
        add_explicit_study_filters(fields, evidence)
        self.assertEqual(fields['majors'], ['德语'])
        self.assertEqual(fields['grades'], ['不限年级'])
        self.assertEqual(evidence['majors'], evidence['eligibility'])

    def test_learning_resource_keeps_paid_access_but_drops_local_download_notes(self):
        row = prepare_resource({'title': '课程', 'summary': '学习模型和数据；不是组委会指定教材。',
                                'access': '免费文档；本机读取失败，未留存全文。'})
        self.assertEqual(row['summary'], '学习模型和数据')
        self.assertNotIn('本机', row['access'])
        self.assertEqual(prepare_resource({'access': '需登录'})['access'], '需登录')

    def test_real_prohibition_survives_editorial_cleanup(self):
        text = '不得跨组别；参赛视频必须同期声，不得后期配音；本轮尚未核验附件。'
        self.assertIn('不得跨组别', clean_text(text))
        self.assertIn('不得后期配音', clean_text(text))
        self.assertNotIn('本轮', clean_text(text))

    def test_fact_before_editorial_clause_survives(self):
        self.assertIn('比赛为个人机试', clean_text('比赛为个人机试，集体报名缴费不代表团队答题。'))

    def test_postmark_is_a_real_submission_rule(self):
        self.assertIn('以邮戳为准', clean_text('报告邮寄7月1日以邮戳为准。'))
        self.assertEqual(clean_text('最终以组委会当年样题为准。'), '')

    def test_education_includes_explicit_abbreviated_list(self):
        self.assertEqual(education_from_eligibility('统招全日制在校本科、专科生'), ['本科', '专科'])
        self.assertEqual(education_from_eligibility('在校研、本、专科学生'), ['本科', '研究生', '专科'])

    def test_topic_does_not_become_major_requirement(self):
        record = {'title': '全国大学生数学建模竞赛', 'catalog_code': '2026074', 'category': '',
                  'aliases': [], 'sources': [{'id': 's1'}], 'fields': {}}
        add_discovery_metadata(record, {'mathematical-modeling'})
        self.assertEqual(record['category'], 'mathematical-modeling')
        self.assertIn('数模', record['aliases'])
        self.assertNotIn('majors', record['fields'])

    def test_foreign_school_quota_does_not_become_general(self):
        text = '该校名额为4队，9月21日截止；该校名额与期限不适用于同济。'
        self.assertEqual(clean_text(text), '')

    def test_host_institution_is_a_fact(self):
        self.assertEqual(clean_text('同济大学承办全国比赛。'), '同济大学承办全国比赛。')

    def test_field_without_valid_source_is_not_promoted(self):
        edition = {'requirements': {'team_size_max': {'value': 5, 'status': 'verified', 'source_id': 'missing'}}}
        self.assertEqual(supported_fields(edition, {'s1': SOURCE})[0], {})

    def test_generated_mapping_requires_exact_fact(self):
        edition = {'requirements': {'registration_deadline': {'value': '2026-11-01',
                    'review_status': 'pending', 'source_ids': ['s1'], 'locator': '字段映射待审核'}}}
        self.assertNotIn('registration_deadline', supported_fields(edition, {'s1': SOURCE})[0])

    def test_teacher_count_is_not_team_size(self):
        edition = {'facts': [{'text': '指导教师最多2人，提交3件作品。', 'source_id': 's1', 'locator': '规则'}]}
        self.assertNotIn('team_size_max', fact_fields(edition, {'s1': SOURCE})[0])

    def test_different_tracks_do_not_create_one_team_limit(self):
        edition = {'facts': [{'text': '每队学生最多3人。', 'source_id': 's1'},
                             {'text': '每队学生最多5人。', 'source_id': 's1'}]}
        self.assertNotIn('team_size_max', fact_fields(edition, {'s1': SOURCE})[0])

    def test_explicit_personal_or_team_range(self):
        edition = {'facts': [{'text': '大学生组可个人或2—20人组队，不得跨组别。', 'source_id': 's1'}]}
        fields, evidence, sources = fact_fields(edition, {'s1': SOURCE})
        self.assertEqual(fields['team_size_min'], 2)
        self.assertEqual(fields['team_size_max'], 20)
        self.assertEqual(fields['participation_type'], 'both')
        self.assertTrue(set(evidence['team_size_max']) <= {s['id'] for s in sources})

    def test_campus_selection_not_accepted_as_national(self):
        source = {**SOURCE, 'title': '关于我校校内选拔赛的通知'}
        edition = {'requirements': {'eligibility': {'value': '全日制本科生', 'status': 'verified', 'source_id': 's1'}}}
        self.assertNotIn('eligibility', supported_fields(edition, {'s1': source})[0])

    def test_identity_only_record_stays_internal(self):
        result, reason = build_edition_record({'code': '2026001', 'name': '比赛', 'identity_status': 'unconfirmed'},
                                             {'year': 2026, 'evidence_status': 'rules'})
        self.assertIsNone(result)
        self.assertEqual(reason, 'identity_or_core_evidence')

    def test_overview_uses_competition_intro_not_research_description(self):
        entry = {'code': '2026001', 'name': '比赛', 'edition_note': '2026届',
                 'overview': '围绕创新项目准备方案与答辩材料。',
                 'competition_sources': [{**SOURCE, 'verified_by': 'page_read', 'summary': '页面提供报名入口。'}]}
        record, _ = build_overview_record(entry, '2026-10-03')
        self.assertEqual(record['summary'], entry['overview'])
        self.assertNotIn('页面提供', str(record['sections']))
        self.assertIsNone(record['competition_id'])


if __name__ == '__main__':
    unittest.main()
