from unittest.mock import patch

from django.test import TestCase

from competition_catalog.models import CatalogEntry, OfficialSite
from ingestion.http import FetchError, Page

from .web import ChatOfficialClient, retrieve_official_web


class OfficialWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        entry = CatalogEntry.objects.create(code='2026001', name='机器人创意大赛', grade='A', levels='全国',
                                            source_url='https://www.tongji.edu.cn/catalog')
        cls.site = OfficialSite.objects.create(entry=entry, url='https://www.tongji.edu.cn/robot',
                                                evidence_url='https://www.tongji.edu.cn/catalog',
                                                allowed_hosts=['www.tongji.edu.cn'])

    def test_only_registry_target_and_actual_page(self):
        class Client:
            def __init__(self, hosts):
                self.hosts = hosts

            def get(self, url):
                self.url = url
                return Page(url, '<html><body><article><h1>机器人创意大赛通知</h1>'
                                 '<p>2026年机器人创意大赛规则已经发布。请查看本页全部内容。</p>'
                                 '<p>参赛安排和截止时间请以新公告为准，未写明报名截止。</p>'
                                 '<p>本通知仅说明机器人作品展示方式，报名资格、报名起始及截止时间以主办方后续发布的完整章程为准。</p>'
                                 '</article></body></html>')

            def close(self):
                pass

        rows, status = retrieve_official_web('机器人创意大赛官网最新通知 https://evil.example/path',
                                              client_factory=Client)
        self.assertEqual(status, 'ready')
        self.assertEqual(rows[0]['url'], self.site.url)
        self.assertEqual(rows[0]['status'], 'unreviewed_official_page')
        self.assertIsNone(rows[0]['published_on'])
        self.assertEqual(retrieve_official_web('随便查一个网站', client_factory=Client)[0], [])

    def test_disabled_site_and_network_failure(self):
        self.site.enabled = False
        self.site.save(update_fields=['enabled'])
        self.assertEqual(retrieve_official_web('机器人创意大赛官网')[1], 'registered_site_not_matched')
        self.site.enabled = True
        self.site.save(update_fields=['enabled'])

        class FailedClient:
            def __init__(self, hosts):
                pass

            def get(self, url):
                raise FetchError('timeout', 'offline')

            def close(self):
                pass

        self.assertEqual(retrieve_official_web('机器人创意大赛官网', client_factory=FailedClient)[1],
                         'official_site_unavailable')

    def test_generic_entry_page_is_not_reported_as_notice(self):
        class IndexClient:
            def __init__(self, hosts):
                pass

            def get(self, url):
                return Page(url, '<html><head><title>机器人创意大赛</title></head><body>'
                                 '<p>机器人创意大赛官方网站欢迎访问。这里展示历届新闻和图片。</p>'
                                 '<p>请从通知列表中选择具体公告；当前首页没有独立通知标题、发布时间或报名规则。</p>'
                                 '<p>参赛资料、活动回顾及获奖展示均可通过网站导航继续查看。</p>'
                                 '</body></html>')

            def close(self):
                pass

        self.assertEqual(retrieve_official_web('机器人创意大赛官网', client_factory=IndexClient),
                         ([], 'official_page_not_a_notice'))

    @patch('ingestion.http.OfficialClient._check_robots', autospec=True)
    def test_chat_does_not_wait_for_long_robots_delay(self, check_robots):
        def set_interval(client, _url):
            client.interval = 30

        check_robots.side_effect = set_interval
        client = ChatOfficialClient(['www.tongji.edu.cn'])
        try:
            with self.assertRaises(FetchError) as error:
                client._check_robots(self.site.url)
            self.assertEqual(error.exception.code, 'robots_delay_unsupported')
        finally:
            client.close()

    def test_redirect_outside_registry_is_rejected(self):
        class RedirectedClient:
            def __init__(self, hosts):
                pass

            def get(self, url):
                return Page('https://outside.example.com/', '<article>很多字</article>')

            def close(self):
                pass

        self.assertEqual(retrieve_official_web('机器人创意大赛官网', client_factory=RedirectedClient)[0], [])
