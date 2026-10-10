"""Resource query behavior, independent of production IDs and external models."""
from django.test import SimpleTestCase

from .resource_retrieval import resource_scores, resource_primary_request
from .unified import _record, _rank, as_evidence, retrieve_unified
from .router import route_query
from unittest.mock import patch


def resource(identifier, title, description='', **fields):
    row = _record('resource', identifier, title, description, description, 'https://www.tongji.edu.cn/' + identifier)
    return {**row, **fields}


class ResourceQueryTests(SimpleTestCase):
    def test_chinese_conversation_can_match_a_short_topic_inside_a_sentence(self):
        rows = [resource('references', '参考文献工具', '整理文献管理与论文引用'),
                resource('drawing', '绘图工具', '绘制流程图')]
        scores, _ = resource_scores(rows, '我想把论文引用和文献管理做好，能推荐工具吗？')
        self.assertIn('references', scores)
        self.assertNotIn('drawing', scores)

    def test_product_initials_do_not_match_arbitrary_english_substrings(self):
        rows = [resource('board', 'RoboMaster开发板C型教程', '嵌入式例程'),
                resource('car', 'Student Formula', '车辆考核'),
                resource('image', 'Image Editor', '支持 ARM64 下载')]
        scores, eligible = resource_scores(rows, 'RM 战队想上手 C 板，有嵌入式例程吗？')
        self.assertEqual(set(scores), {'board'})
        self.assertEqual(eligible, {'board'})

    def test_english_alternatives_and_comparisons_keep_both_names(self):
        rows = [resource('python', 'Python教程'), resource('java', 'Java教程'),
                resource('javascript', 'JavaScript教程')]
        scores, _ = resource_scores(rows, 'Python 或 Java 的教程，分别介绍')
        self.assertEqual(set(scores), {'python', 'java'})
        scores, _ = resource_scores(rows, 'Java 入门教程')
        self.assertEqual(set(scores), {'java'})

    def test_exact_title_navigation_excludes_products_that_only_mention_the_language(self):
        rows = [resource('language', 'Python官方教程', '语法与数据结构'),
                resource('vision', 'ImageLib Python教程', 'Python视觉分析'),
                resource('simulation', 'Simulation Python文档', 'Python仿真')]
        scores, eligible = resource_scores(rows, '请帮我找一下 Python官方教程，给我资料入口。')
        self.assertEqual(set(scores), {'language'})
        self.assertEqual(eligible, {'language'})

    def test_learning_and_excluded_notices_cannot_be_reintroduced_by_semantics(self):
        catalog = [{'code': 'event', 'name': '创新杯程序设计竞赛', 'aliases': []}]
        rows = [resource('language', 'Python官方教程', '语法和数据结构', catalogs=catalog),
                resource('rules', '创新杯规程与报名指南', 'Python组报名通知', catalogs=catalog),
                resource('vision', 'Python视觉教程', '数据结构',
                         catalogs=[{'code': 'vision', 'name': '图像杯', 'aliases': []}])]
        with patch('ai_services.unified.semantic_search', return_value={
                ('resource', 'rules'): .99, ('resource', 'vision'): .98, ('resource', 'language'): .65}):
            ranked, _, _ = _rank(rows, '准备创新杯 Python组，学习语法和数据结构教程，不要报名通知', 'smart')
        self.assertEqual([row['object_id'] for row in ranked], ['language'])

    def test_event_problem_request_enforces_real_event_type_and_edition(self):
        event = [{'code': 'model', 'name': '大学生数学建模竞赛', 'aliases': ['数模']}]
        other = [{'code': 'translation', 'name': '大学生笔译竞赛', 'aliases': []}]
        rows = [resource('current', '2026年求知杯赛题发布页', '赛题与题目附件', catalogs=event),
                resource('old', '2025年求知杯赛题发布页', '赛题与题目附件', catalogs=event),
                resource('rules', '2026年求知杯报名通知', '报名指南', catalogs=event),
                resource('other', '2026年笔译样题', '赛题与题目附件', catalogs=other)]
        with patch('ai_services.unified.semantic_search', return_value={
                ('resource', row['object_id']): .99 for row in rows}):
            ranked, _, _ = _rank(rows, '2026年求知杯数模赛题和题目附件入口', 'resource')
        self.assertEqual([row['object_id'] for row in ranked], ['current'])

    def test_weak_topic_overlap_does_not_gain_admission_from_trust_and_relations(self):
        rows = [resource('diagnostics', '回归诊断示例', '检查残差和异方差的代码示例'),
                resource('table', '表格筛选教程', '数据筛选及列选取', verified_at='2026-10-10T00:00:00Z',
                         named_associations=[{'object_type': 'competition', 'object_id': str(i),
                                              'title': '市场调查与数据分析大赛'} for i in range(5)])]
        with patch('ai_services.unified.semantic_search', return_value={
                ('resource', 'diagnostics'): .78, ('resource', 'table'): .61}):
            ranked, _, _ = _rank(rows, '市场调查数据回归分析后，检查残差和异方差，有带代码的诊断示例吗', 'smart')
        self.assertEqual([row['object_id'] for row in ranked], ['diagnostics'])

    def test_relevant_alternatives_remain_available_after_admission_filter(self):
        rows = [resource('python', 'Python入门教程'), resource('java', 'Java入门教程')]
        with patch('ai_services.unified.semantic_search', return_value={}):
            ranked, _, _ = _rank(rows, 'Python或Java入门教程都可以', 'resource')
        self.assertEqual({row['object_id'] for row in ranked}, {'python', 'java'})

    def test_competition_name_is_satisfied_by_a_real_named_relation(self):
        rows = [resource('algorithms', '算法课程习题', '训练证明和复杂度分析',
                         named_associations=[{'object_type': 'competition', 'object_id': 'db-99',
                                              'title': 'CCPC程序设计竞赛'}]),
                resource('letter', 'CCPC邀请函', '核对参赛名单与报名')]
        scores, _ = resource_scores(rows, '打 CCPC，想学算法证明和复杂度分析，有习题资料吗？')
        self.assertGreater(scores['algorithms'], scores.get('letter', 0))

    def test_unavailable_named_course_cannot_match_a_generic_description(self):
        rows = [resource('other', '神经网络课程', '课程提供图像算法的学习资料')]
        scores, eligible = resource_scores(rows, '我只想找 CS9999 神经网络课程的资料')
        self.assertEqual(scores, {})
        self.assertEqual(eligible, set())

    def test_semantic_match_does_not_require_any_keyword_overlap(self):
        rows = [resource('language', 'Python官方教程', '基础语法与程序设计')]
        question = '想入门编程，有适合新人的资料吗？'
        scores, eligible = resource_scores(rows, question)
        self.assertEqual(scores, {})
        self.assertEqual(eligible, {'language'})
        with patch('ai_services.unified.semantic_search', return_value={('resource', 'language'): .99}):
            ranked, _, mode = _rank(rows, question, 'resource')
        self.assertEqual([row['object_id'] for row in ranked], ['language'])
        self.assertEqual(mode, 'hybrid')

    def test_known_tool_name_cannot_bypass_an_explicit_missing_course_identifier(self):
        rows = [resource('language', 'Python官方教程', '基础语法与程序设计'),
                resource('other-course', 'CS1234 Python课程')]
        question = '我只要 CS9999 的 Python 教程，不要其他课程'
        scores, eligible = resource_scores(rows, question)
        self.assertEqual(scores, {})
        self.assertEqual(eligible, set())
        with patch('ai_services.unified.semantic_search', return_value={('resource', 'language'): .99}):
            ranked, _, _ = _rank(rows, question, 'resource')
        self.assertEqual(ranked, [])

    def test_explicit_identifier_allows_real_matches_and_course_alternatives(self):
        rows = [resource('first', 'CS1234 Python课程'), resource('second', 'CS5678 Python课程'),
                resource('generic', 'Python课程')]
        scores, eligible = resource_scores(rows, '比较 CS1234 或 CS5678 的 Python 课程')
        self.assertEqual(set(scores), {'first', 'second'})
        self.assertEqual(eligible, {'first', 'second'})
        _, eligible = resource_scores([resource('generic', 'MIT Python课程')], 'MIT 6.099 课程资料')
        self.assertEqual(eligible, set())

    def test_material_scope_preserves_explicit_mixed_requests(self):
        for question in ['CCPC备赛有没有算法课作业，提供解答', '机器人比赛控制编程资料',
                         '科研 AI 技能可以帮助文献检索吗']:
            with self.subTest(question=question):
                self.assertTrue(resource_primary_request(question))
        for question in ['机器人科研竞赛资源', '比较机器人科研和竞赛，再给学习资料',
                         '推荐机器人比赛和控制编程资料', '控制编程教程，也推荐机器人比赛']:
            with self.subTest(question=question):
                self.assertFalse(resource_primary_request(question))

    def test_lab_publications_remain_research_but_paper_tools_remain_resources(self):
        question = '某实验室发表了哪些论文或科研成果？'
        self.assertFalse(resource_primary_request(question))
        row = _record('research_opportunity', 'lab', '某实验室', '论文与科研成果',
                      '公开发表论文', 'https://www.tongji.edu.cn/lab')
        row['retrieval_score'] = .99
        with patch('ai_services.unified.public_secondary_records', return_value=[row]), \
                patch('ai_services.unified._rank', return_value=([row], [], 'hybrid')):
            result = retrieve_unified(question, 'smart', route_query(question))
        self.assertEqual([item['object_id'] for item in result['records']], ['lab'])
        for material in ['工具', '插件', '技能']:
            with self.subTest(material=material):
                self.assertTrue(resource_primary_request(f'找帮助科研论文整理的{material}'))

    def test_functional_request_can_rank_a_plugin_above_the_product(self):
        rows = [resource('manager', 'PaperBox', '论文文献管理'),
                resource('plugin', 'Stable Keys for PaperBox', '自动导出引用键，保持引用键稳定')]
        scores, _ = resource_scores(rows, '用 PaperBox 写论文，想自动导出并让引用键保持稳定，找哪个插件？')
        self.assertGreater(scores['plugin'], scores['manager'])

    def test_named_relations_survive_even_when_the_target_is_after_three_links(self):
        names = [{'object_type': 'competition', 'object_id': f'db-{number}', 'title': title}
                 for number, title in enumerate(['甲赛事', '乙赛事', '丙赛事', '目标算法赛'], start=1)]
        row = resource('algorithms', '算法课程', '算法证明', named_associations=names,
                       related_object_ids={'competition': [item['object_id'] for item in names]})
        with patch('ai_services.unified.semantic_search', return_value={}):
            ranked, _, _ = _rank([row], '目标算法赛学习资料', 'resource')
        evidence = as_evidence(ranked[0])
        self.assertEqual(evidence['named_associations'][0]['title'], '目标算法赛')
        self.assertIn('目标算法赛', evidence['text'])
        self.assertEqual(len(evidence['related_object_ids']['competition']), 4)
