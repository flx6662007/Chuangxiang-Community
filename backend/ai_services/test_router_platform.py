from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from resources.models import Resource, ResourceTaxonomy

from .chat import chat
from .platform import retrieve_platform
from .router import route_query


class RouterTests(SimpleTestCase):
    def test_domains_and_intents(self):
        cases = [
            ('你好', 'general', ('other',)),
            ('有哪些机器人比赛', 'platform', ('competition',)),
            ('实验室科研项目官网最新通知', 'hybrid', ('project',)),
            ('竞赛规则资料', 'hybrid', ('competition',)),
            ('请联网查官网', 'web', ('other',)),
            ('怎么组队', 'platform', ('team',)),
        ]
        for question, intent, domains in cases:
            with self.subTest(question=question):
                result = route_query(question)
                self.assertEqual(result.intent, intent)
                self.assertEqual(result.domains, domains)

    def test_platform_context_is_data_and_history_is_unchanged(self):
        class Provider:
            def complete_text(self, messages):
                self.messages = messages
                return '尚未查到可确认的赛事。'

        provider = Provider()
        with patch('ai_services.chat.retrieve_platform', return_value=[{
            'kind': 'competition', 'entity_id': 'db-1', 'version': 'v1', 'title': '机器人比赛',
            'url': 'https://www.tongji.edu.cn/robot', 'internal_url': '/competitions/1',
            'text': '机器人比赛规则', 'verified_at': '2026-10-04', 'published_on': None,
            'status': 'unknown', 'status_note': '截止未知',
        }]) as retrieval:
            result = chat([{'role': 'user', 'content': '机器人比赛'}], client=provider)
        self.assertEqual(result['role'], 'assistant')
        self.assertEqual(provider.messages[-1], {'role': 'user', 'content': '机器人比赛'})
        self.assertEqual(provider.messages[1]['role'], 'user')
        self.assertIn('PLATFORM_CONTEXT', provider.messages[1]['content'])
        retrieval.assert_called_once()


class ResourceRetrieverTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = ResourceTaxonomy.objects.create(code='ai-test', kind='category', name='测试分类')

    def resource(self, title, status, available='available', verified=True):
        return Resource.objects.create(
            title=title, description='机器人课程', category=self.category,
            access_url='https://www.tongji.edu.cn/course', publication_status=status,
            availability=available, last_verified_at=timezone.now() if verified else None,
            published_at=timezone.now() if status != 'draft' else None,
            withdrawal_reason='已撤下' if status == 'withdrawn' else '',
        )

    def test_only_real_published_available_resources_with_actual_verification_times(self):
        route = route_query('机器人资源')
        self.assertEqual(retrieve_platform('机器人资源', route), [])
        public = self.resource('机器人公开课程', 'published')
        self.resource('机器人草稿课程', 'draft')
        self.resource('机器人下架课程', 'withdrawn')
        self.resource('机器人不可用课程', 'published', available='unavailable')
        direct = self.resource('机器人直接发布课程', 'published', verified=False)
        rows = retrieve_platform('机器人资源', route)
        self.assertEqual({row['entity_id'] for row in rows}, {str(public.pk), str(direct.pk)})
        by_id = {row['entity_id']: row for row in rows}
        self.assertEqual(by_id[str(public.pk)]['verified_at'], public.last_verified_at.isoformat())
        self.assertIsNone(by_id[str(direct.pk)]['verified_at'])
        self.assertEqual(by_id[str(direct.pk)]['status_note'], '学习资源')

    def test_match_is_not_limited_to_newest_hundred_resources(self):
        older = self.resource('天文学课程', 'published', verified=False)
        for index in range(101):
            self.resource(f'机器人课程{index}', 'published', verified=False)
        rows = retrieve_platform('天文学资源', route_query('天文学资源'))
        self.assertEqual([row['entity_id'] for row in rows], [str(older.pk)])

    def test_private_contact_line_does_not_create_a_search_match(self):
        row = self.resource('公开课程', 'published', verified=False)
        row.description = '学习说明\n联系人：秘密联系词'
        row.save()
        self.assertEqual(retrieve_platform('秘密联系词资源', route_query('秘密联系词资源')), [])
