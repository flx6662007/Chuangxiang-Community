"""公开知识检索的权限边界、来源隐私和结果语义。"""
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import include, path

from curation.test_api import LibraryAPIFixtures
from .views import AssistantSearchThrottle

urlpatterns = [path('api/v1/assistant/', include('ai_services.urls'))]


@override_settings(ROOT_URLCONF=__name__)
class AssistantSearchTests(LibraryAPIFixtures, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def search(self, query):
        return self.client.get('/api/v1/assistant/search/', {'q': query})

    def test_synonyms_search_public_current_body_and_return_catalog_contract(self):
        self.make_document('ai-guide', 'published', self.catalog, body='人工智能方法与视觉系统')
        response = self.search('我是大二学生，对 AI 感兴趣，希望找一个适合组队的比赛')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['mode'], 'keyword')
        self.assertEqual(response.data['keywords'], ['人工智能'])
        row = response.data['results'][0]
        self.assertEqual(row['catalog']['code'], self.catalog.code)
        self.assertEqual(row['match_reason'], '公开资料：人工智能')
        self.assertEqual(row['catalog']['document_count'], 2)
        self.assertIn('resource_count', row['catalog'])
        self.assertNotIn('interpretation', response.data)

    def test_arbitrary_keywords_and_catalog_code_work(self):
        self.make_document('astronomy', 'published', self.catalog, body='天文学观察与研究')
        self.assertEqual(self.search('帮我找天文学相关的赛事').data['count'], 1)
        self.assertEqual(self.search(self.catalog.code).data['results'][0]['catalog']['code'], self.catalog.code)

    def test_draft_withdrawn_and_unpublished_dependencies_cannot_match(self):
        self.make_document('draft-special', 'draft', self.catalog, body='秘密关键词')
        self.make_document('withdrawn-special', 'withdrawn', self.catalog, body='秘密关键词')
        self.make_document('hidden-dependency', 'published', self.catalog, self.draft_resource, body='秘密关键词')
        self.make_document('hidden-edition', 'published', self.catalog, competition=self.withdrawn_competition, body='秘密关键词')
        self.assertEqual(self.search('秘密关键词').data['count'], 0)

    def test_disabled_and_demo_records_are_excluded(self):
        self.make_document('inactive', 'published', self.inactive_catalog, body='特有方向')
        self.make_document('demo-search', 'published', self.catalog, body='特有方向')
        demo = self.make_competition('demo-search-competition')
        self.make_document('linked-demo', 'published', self.catalog, competition=demo, body='特有方向')
        self.assertEqual(self.search('特有方向').data['count'], 0)

    def test_old_revision_is_not_searchable_after_current_pointer_changes(self):
        document = self.make_document('versioned', 'published', self.catalog, body='旧独有内容')
        document.current_revision = self.make_revision(document, 2, self.catalog, body='新独有内容')
        document.save()
        self.assertEqual(self.search('旧独有内容').data['count'], 0)
        self.assertEqual(self.search('新独有内容').data['count'], 1)

    def test_contacts_source_metadata_and_paths_do_not_affect_matching_or_escape(self):
        self.make_document('privacy-guide', 'published', self.catalog,
            body='公开的天文学说明\n联系人：秘密联系词\n邮箱：hidden@tongji.edu.cn',
            sources=[{'url': 'https://www.tongji.edu.cn/?token=secret', 'title': '隐秘来源词'}],
            metadata={'private_path': 'C:/private/隐秘文件词.pdf', 'operator_email': 'hidden@tongji.edu.cn'})
        for word in ('秘密联系词', '隐秘来源词', '隐秘文件词'):
            self.assertEqual(self.search(word).data['count'], 0)
        self.catalog.source_url = 'https://www.tongji.edu.cn/?token=secret'
        self.catalog.save()
        data = self.search('天文学').data
        self.assertEqual(data['results'][0]['catalog']['source_url'], '')
        self.assertNotIn('secret', str(data))
        self.assertNotIn('hidden@', str(data))
        self.assertNotIn('C:/private', str(data))

    def test_empty_long_input_and_no_match(self):
        for query in ('', '  ', 'x' * 501):
            self.assertEqual(self.search(query).status_code, 400)
        self.assertEqual(self.search('近期可以报名的比赛').data['keywords'], [])
        self.assertEqual(self.search('不存在的火星主题').data['results'], [])

    def test_results_are_bounded_ordered_and_use_only_local_reads(self):
        for index in range(10):
            self.make_catalog(f'20261{index:02}', name=f'天文学比赛{index}')
        with patch('socket.create_connection', side_effect=AssertionError('network not required')):
            response = self.search('天文学')
        self.assertEqual(response.data['count'], 10)
        self.assertEqual(len(response.data['results']), 8)
        codes = [row['catalog']['code'] for row in response.data['results']]
        self.assertEqual(codes, sorted(codes))
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_short_latin_aliases_do_not_match_inside_other_words(self):
        self.make_document('training-guide', 'published', self.catalog, body='training examples')
        self.assertEqual(self.search('AI').data['count'], 0)

    def test_search_is_rate_limited(self):
        with patch.object(AssistantSearchThrottle, 'rate', '2/min'):
            self.assertEqual(self.search('工程').status_code, 200)
            self.assertEqual(self.search('工程').status_code, 200)
            self.assertEqual(self.search('工程').status_code, 429)
