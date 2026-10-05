"""公开资料接口：发布边界、当前版本、隐私字段和分页。"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import include, path
from django.utils import timezone

from newsletters.models import Newsletter, NewsletterItem, NewsletterRevision
from research.models import ResearchOpportunity

urlpatterns = [path('editorial/', include('information_library.public_urls'))]


@override_settings(ROOT_URLCONF=__name__)
class PublicEditorialTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(email='editorial@tongji.edu.cn', password='tests-only')

    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.editorial_path = Path(folder.name) / 'editorial.json'
        self.write_editorial()
        mocked = patch('information_library.selectors.EDITORIAL_PATH', self.editorial_path)
        mocked.start()
        self.addCleanup(mocked.stop)

    def write_editorial(self, laboratories=None, newsletters=None):
        self.editorial_path.write_text(json.dumps({'laboratories': laboratories or [], 'newsletters': newsletters or []}), encoding='utf-8')

    def research(self, code='public-lab', status='published', **overrides):
        values = dict(code=code, title='智能机器人研究', description='机器人与感知研究', summary='机器人工程实践',
                      recruiting_entity='本科科研团队', official_url=f'https://cs.tongji.edu.cn/{code}',
                      publication_status=status, published_at=timezone.now() if status != 'draft' else None,
                      withdrawal_reason='内部下架记录' if status == 'withdrawn' else '',
                      application_email='secret@tongji.edu.cn', verification_note='内部秘密')
        values.update(overrides)
        return ResearchOpportunity.objects.create(**values)

    def newsletter(self, code='public-news', target=None):
        item = Newsletter.objects.create(code=code, created_by=self.actor)
        revision = NewsletterRevision.objects.create(newsletter=item, version=1, title='本期快讯',
                    introduction='本期导读', created_by=self.actor, updated_by=self.actor)
        data = dict(revision=revision, position=1, title_snapshot='公开讲座', summary_snapshot='机器人讲座',
                    kind='activity', source_url='https://www.tongji.edu.cn/lecture')
        if target:
            data.update(kind='research', research=target, source_version=target.content_version,
                        source_url=target.official_url)
        NewsletterItem.objects.create(**data)
        revision.status, revision.confirmed_at, revision.confirmed_by = 'confirmed', timezone.now(), self.actor
        revision.save()
        item.current_revision, item.publication_status, item.published_at = revision, 'published', timezone.now()
        item.save()
        return item, revision

    def test_anonymous_research_uses_only_public_nondemo_fields(self):
        self.research(description='公开说明\n邮箱：secret@tongji.edu.cn', summary='<b>公开摘要</b> 13812345678',
                      requirements='能力要求\n联系人：内部姓名')
        self.research('draft-lab', 'draft')
        self.research('withdrawn-lab', 'withdrawn')
        self.research('demo-lab')
        response = self.client.get('/editorial/research/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        card = data['results'][0]
        self.assertEqual(set(card), {'id', 'title', 'unit', 'date', 'verifiedOn', 'summary', 'participation', 'evidenceNote', 'sourceUrl', 'direction'})
        self.assertEqual(card['date'], '')
        self.assertEqual(card['verifiedOn'], '')
        for private in ('secret@', '13812345678', '内部', '<b>', 'application_email'):
            self.assertNotIn(private, response.content.decode())
        self.assertEqual(self.client.post('/editorial/research/').status_code, 405)

    def test_json_is_sanitized_deduplicated_and_database_withdrawal_wins(self):
        url = 'https://cs.tongji.edu.cn/curated'
        self.write_editorial(laboratories=[
            {'id': 'visible', 'title': '官方实验室', 'sourceUrl': url, 'summary': '<b>学习材料</b>'},
            {'id': 'duplicate', 'title': '重复实验室', 'sourceUrl': url},
            {'id': 'private', 'title': '私人', 'sourceUrl': 'http://127.0.0.1/secrets'},
            {'id': 'hidden', 'title': '隐藏草稿', 'sourceUrl': 'https://cs.tongji.edu.cn/hidden', 'publication_status': 'draft'},
            {'id': 'demo-fake', 'title': '演示数据', 'sourceUrl': 'https://cs.tongji.edu.cn/demo'},
        ])
        response = self.client.get('/editorial/research/').json()
        self.assertEqual(response['count'], 1)
        self.assertEqual(response['results'][0]['summary'], '学习材料')
        self.research('withdrawn-match', 'withdrawn', official_url=url)
        self.assertEqual(self.client.get('/editorial/research/').json()['count'], 0)

    def test_database_record_replaces_editorial_with_same_source(self):
        item = self.research()
        self.write_editorial(laboratories=[{'id': 'old-copy', 'title': '旧文案', 'sourceUrl': item.official_url}])
        data = self.client.get('/editorial/research/').json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['id'], f'db-{item.pk}')

    def test_search_all_words_pagination_and_invalid_parameters(self):
        for index in range(3):
            self.research(f'lab-{index}')
        data = self.client.get('/editorial/research/', {'search': '智能 机器人', 'page_size': 2}).json()
        self.assertEqual(data['count'], 3)
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(len(self.client.get('/editorial/research/', {'page_size': 2, 'page': 2}).json()['results']), 1)
        self.assertEqual(self.client.get('/editorial/research/', {'search': '不存在'}).json()['count'], 0)
        for params in ({'search': 'x' * 201}, {'page_size': 0}, {'page_size': 'x'}):
            self.assertEqual(self.client.get('/editorial/research/', params).status_code, 400)
        self.assertEqual(self.client.get('/editorial/research/', {'page': 999}).status_code, 404)

    def test_newsletter_current_public_revision_only(self):
        item, revision = self.newsletter()
        NewsletterRevision.objects.create(newsletter=item, version=2, title='未公开新稿', introduction='内部计划',
                    created_by=self.actor, updated_by=self.actor)
        response = self.client.get('/editorial/newsletters/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)
        self.assertEqual(response.json()['results'][0]['title'], revision.title)
        self.assertNotIn('未公开', response.content.decode())
        self.assertNotIn('内部计划', response.content.decode())

    def test_withdrawn_newsletter_does_not_reappear_from_editorial(self):
        item, _ = self.newsletter()
        item.publication_status, item.withdrawal_reason = 'withdrawn', '内部原因'
        item.save()
        self.write_editorial(newsletters=[{'id': 'old-news', 'title': '已下架快讯', 'sourceUrl': 'https://www.tongji.edu.cn/lecture'}])
        self.assertEqual(self.client.get('/editorial/newsletters/').json()['count'], 0)

    def test_removed_or_changed_newsletter_reference_and_introduction_hidden(self):
        target = self.research(last_verified_at=timezone.now())
        self.newsletter(target=target)
        self.assertEqual(self.client.get('/editorial/newsletters/').json()['count'], 1)
        ResearchOpportunity.objects.filter(pk=target.pk).update(content_version=2)
        self.assertEqual(self.client.get('/editorial/newsletters/').json()['count'], 0)
        ResearchOpportunity.objects.filter(pk=target.pk).update(content_version=1, publication_status='withdrawn', withdrawal_reason='维护')
        self.assertEqual(self.client.get('/editorial/newsletters/').json()['count'], 0)

    def test_empty_newsletter_endpoint_remains_empty(self):
        self.assertEqual(self.client.get('/editorial/newsletters/').json()['count'], 0)
