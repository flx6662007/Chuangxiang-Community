"""Unified retrieval acceptance cases; no network or model request is made."""

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from competitions.models import Competition, CompetitionSource, CompetitionTaxonomy
from research.models import ResearchOpportunity
from resources.models import Resource, ResourceCompetition, ResourceResearchOpportunity, ResourceTaxonomy

from .evidence import external_decision, source_trust
from .router import route_query
from .unified import as_evidence, public_secondary_records, recommendations, retrieve_unified
from .web import search_external


@override_settings(PUBLIC_RESEARCH_ENABLED=True, COMPETITION_CATALOG_ONLY=False)
class UnifiedRetrievalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        category = CompetitionTaxonomy.objects.create(code='robot-unit', kind='category', name='机器人')
        cls.competition = Competition.objects.create(
            code='robot-unit', title='机器人创意大赛', edition='2026', summary='本科生机器人设计与展示',
            description='面向本科生的机器人创意竞赛', category=category, organizer='某高校',
            publication_status='published', published_at=now, last_verified_at=now,
        )
        CompetitionSource.objects.create(
            competition=cls.competition, source_type='official', source_name='赛事通知',
            source_url='https://www.tongji.edu.cn/robot-notice', is_primary=True, last_verified_at=now,
        )
        resource_category = ResourceTaxonomy.objects.create(code='course-unit', kind='category', name='学习课程')
        cls.related_resource = Resource.objects.create(
            code='control-course-unit', title='控制编程基础教程', description='控制编程基础学习材料',
            category=resource_category, access_url='https://www.tongji.edu.cn/control-course',
            publication_status='published', availability='available', published_at=now, last_verified_at=now,
        )
        cls.python_resource = Resource.objects.create(
            code='python-course-unit', title='Python 入门课程', description='Python 初学者学习资源',
            category=resource_category, access_url='https://www.tongji.edu.cn/python-course',
            publication_status='published', availability='available', published_at=now, last_verified_at=now,
        )
        Resource.objects.create(
            code='private-course-unit', title='Python 私有草稿', description='不得进入回答',
            category=resource_category, access_url='https://www.tongji.edu.cn/private-course',
            publication_status='draft', availability='available',
        )
        ResourceCompetition.objects.create(resource=cls.related_resource, competition=cls.competition)
        cls.opportunity = ResearchOpportunity.objects.create(
            code='robot-research-unit', title='机器人导航本科生科研机会', description='机器人导航算法研究',
            recruiting_entity='某高校实验室', official_url='https://www.tongji.edu.cn/research-notice',
            research_group='导航算法课题组', publication_status='published', published_at=now,
            last_verified_at=now,
        )
        ResourceResearchOpportunity.objects.create(resource=cls.related_resource, opportunity=cls.opportunity)

    def retrieve(self, question, mode):
        return retrieve_unified(question, mode, route_query(question, mode=mode))

    def curated_competition(self):
        # The competition search implementation has its own corpus tests. This
        # fixture tests how its published hit joins the existing relation table.
        source = {'id': 'source-1', 'url': 'https://www.tongji.edu.cn/robot-notice',
                  'verified_at': timezone.now().isoformat(), 'locator': '赛事通知'}
        hit = {'record_id': 'competition-document-1', 'title': self.competition.title,
               'summary': self.competition.summary, 'edition': '2026', 'category': {'name': '机器人'},
               'score': 1.0, 'content_hash': 'verified-version-1', 'evidence': [source],
               'passages': [{'text': '本科生机器人设计与展示', 'evidence_ids': ['source-1']} ]}
        return {'results': [{'record_id': hit['record_id'], 'competition': {'id': self.competition.pk}}],
                'hits': [hit], 'mode_used': 'keyword', 'warnings': []}

    def test_exact_competition_name_expands_real_resource_relation(self):
        with patch('ai_services.unified.search_competitions', return_value=self.curated_competition()):
            result = self.retrieve('机器人创意大赛', 'competition')
        keys = {(row['object_type'], row['object_id']) for row in result['records']}
        self.assertIn(('competition', 'competition-document-1'), keys)
        self.assertIn(('resource', self.related_resource.code), keys)
        self.assertTrue(result['knowledge_rows'])
        match = next(row for row in result['records'] if row['object_type'] == 'competition')
        self.assertIn(self.related_resource.code, match['related_object_ids']['resource'])
        self.assertEqual(recommendations(result['records'])[0]['related_resources'][0]['title'],
                         self.related_resource.title)

    def test_fuzzy_competition_need_keeps_competition_first(self):
        with patch('ai_services.unified.search_competitions', return_value=self.curated_competition()):
            result = self.retrieve('想找机器人设计比赛', 'competition')
        self.assertEqual(result['records'][0]['object_type'], 'competition')
        self.assertEqual(result['records'][0]['object_id'], 'competition-document-1')

    def test_direct_published_competition_is_not_lost_without_curated_document(self):
        empty_curation = {'results': [], 'hits': [], 'mode_used': 'keyword', 'warnings': []}
        with patch('ai_services.unified.search_competitions', return_value=empty_curation):
            result = self.retrieve('机器人创意大赛', 'competition')
        self.assertIn(('competition', f'db-{self.competition.pk}'),
                      {(row['object_type'], row['object_id']) for row in result['records']})
        direct = next(row for row in result['records'] if row['object_id'] == f'db-{self.competition.pk}')
        self.assertEqual(as_evidence(direct)['internal_url'], f'/competitions/{self.competition.pk}')

    def test_learning_resource_request_filters_drafts(self):
        result = self.retrieve('Python 入门资源', 'resource')
        self.assertEqual(result['records'][0]['object_id'], self.python_resource.code)
        self.assertNotIn('private-course-unit', {row['object_id'] for row in result['records']})

    def test_smart_mode_keeps_relevant_competition_and_research(self):
        with patch('ai_services.unified.search_competitions', return_value=self.curated_competition()):
            result = self.retrieve('机器人科研竞赛资源', 'smart')
        kinds = {row['object_type'] for row in result['records']}
        self.assertIn('competition', kinds)
        self.assertIn('research_opportunity', kinds)

    def test_research_direction_expands_resource_without_fabricating_group(self):
        result = self.retrieve('机器人导航科研方向', 'research')
        keys = {(row['object_type'], row['object_id']) for row in result['records']}
        self.assertIn(('research_opportunity', f'db-{self.opportunity.pk}'), keys)
        self.assertIn(('resource', self.related_resource.code), keys)
        self.assertNotIn('research_group', {row['object_type'] for row in result['records']})
        opportunity = next(row for row in result['records'] if row['object_type'] == 'research_opportunity')
        self.assertEqual(opportunity['research_group_label'], '导航算法课题组')

    def test_missing_vector_index_uses_keyword(self):
        with patch.dict('os.environ', {'UNIFIED_SEMANTIC_INDEX': ''}):
            result = self.retrieve('Python 入门资源', 'resource')
        self.assertEqual(result['mode_used'], 'keyword')
        self.assertIn('unified_index_unconfigured', result['warnings'])
        self.assertEqual(result['records'][0]['object_id'], self.python_resource.code)

    def test_future_group_selector_accepts_only_public_verified_records(self):
        class Selector:
            def public_records(self):
                base = {'object_type': 'research_group', 'object_id': 'group-1', 'title': '导航组',
                        'summary': '机器人导航', 'content': '机器人导航研究',
                        'source_url': 'https://www.tongji.edu.cn/group', 'verified_at': timezone.now().isoformat(),
                        'version': '1', 'status': 'published'}
                return [base, {**base, 'object_id': 'draft-group', 'status': 'draft'}]

        records = public_secondary_records(group_selector=Selector())
        self.assertIn(('research_group', 'group-1'), {(row['object_type'], row['object_id']) for row in records})
        self.assertNotIn('draft-group', {row['object_id'] for row in records})


class EvidencePolicyTests(SimpleTestCase):
    def test_internal_sufficiency_and_external_triggers(self):
        rows = [{'retrieval_score': 0.8}, {'retrieval_score': 0.7}]
        self.assertEqual(external_decision('机器人比赛', route_query('机器人比赛'), rows),
                         (False, 'internal_evidence_sufficient'))
        self.assertEqual(external_decision('机器人比赛', route_query('机器人比赛'), rows[:1])[1],
                         'insufficient_internal_results')
        self.assertEqual(external_decision('机器人比赛', route_query('机器人比赛'),
                                           [{'retrieval_score': 0.2}] * 2)[1], 'low_internal_confidence')
        self.assertEqual(external_decision('机器人比赛官网', route_query('机器人比赛官网'), rows)[1],
                         'explicit_external_request')
        self.assertEqual(external_decision('今年机器人比赛', route_query('今年机器人比赛'), rows)[1],
                         'time_sensitive')

    def test_external_adapter_cannot_self_assign_official_trust(self):
        class SearchAdapter:
            def search(self, query):
                return ([{'kind': 'web', 'title': '第三方网页', 'url': 'https://www.tongji.edu.cn/page',
                          'text': '网页说明', 'source_type': 'official_event',
                          'verified_at': timezone.now().isoformat(), 'reviewed': True,
                          'published_on': 'not-a-date'}], 'ready')

        rows, status = search_external('机器人比赛', adapters=[SearchAdapter()])
        self.assertEqual(status, 'ready')
        self.assertEqual(rows[0]['source_type'], 'ordinary_web')
        self.assertFalse(rows[0]['reviewed'])
        self.assertIsNone(rows[0]['verified_at'])
        self.assertIsNone(rows[0]['published_on'])
        self.assertTrue(rows[0]['read_at'])
        self.assertLess(rows[0]['trust_score'], source_trust('approved_knowledge', reviewed=True).score)
        self.assertLess(rows[0]['evidence_score'], 0.6)

    def test_external_candidates_with_same_url_are_deduplicated(self):
        class SearchAdapter:
            def search(self, query):
                row = {'title': '同一通知', 'url': 'https://www.tongji.edu.cn/notice', 'text': '通知正文'}
                return [row, dict(row)], 'ready'

        rows, status = search_external('通知', adapters=[SearchAdapter()])
        self.assertEqual(status, 'ready')
        self.assertEqual(len(rows), 1)
