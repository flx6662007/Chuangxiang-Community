from types import SimpleNamespace
from contextlib import nullcontext
from unittest.mock import patch
from datetime import date

from django.test import SimpleTestCase, TestCase

from ingestion.http import Page
from .models import CatalogEntry, OfficialSite
from .monitor import discover, parse_page, sync_site


class NoticeDiscoveryTests(SimpleTestCase):
    def setUp(self):
        self.site = SimpleNamespace(
            dedicated=True, allowed_hosts=['contest.example'],
            entry=SimpleNamespace(name='全国大学生计算机竞赛', aliases=[]),
        )

    @patch('competition_catalog.monitor.timezone.localdate', return_value=date(2030, 9, 1))
    def test_new_registration_notice_precedes_awards_and_old_notices(self, _):
        page = Page('https://contest.example/', '''
            <a href="/award">2030年全国大学生计算机竞赛获奖名单</a>
            <a href="/old">2029年全国大学生计算机竞赛报名通知</a>
            <a href="/current">2030年全国大学生计算机竞赛报名通知</a>
            <a href="https://other.example/notice">2030年报名通知</a>
        ''')
        self.assertEqual(discover(self.site, page), [
            'https://contest.example/current', 'https://contest.example/award',
            'https://contest.example/old',
        ])

    def test_specific_article_body_excludes_sidebar_dates(self):
        page = Page('https://contest.example/current', '''
            <title>2030年全国大学生计算机竞赛报名通知</title><article>
            <div class="entry-content"><p>报名截止日期为2030年10月1日。</p><p>'''
            + '本通知面向全国普通高校在校大学生，具体参赛资格和报名要求请阅读赛事规程。' * 3
            + '''</p></div><aside>2039年报名截止日期12月31日</aside></article>''')
        parsed = parse_page(self.site, page)
        self.assertIn('2030年10月1日', parsed['body'])
        self.assertNotIn('2039年', parsed['body'])


class AttachmentHistoryTests(TestCase):
    @patch('competition_catalog.monitor.source_mutex', return_value=nullcontext(True))
    def test_html_rotation_does_not_evict_all_attachment_attempts(self, _):
        entry = CatalogEntry.objects.create(code='2030001', name='全国大学生计算机竞赛', grade='A', source_url='https://school.example/catalog')
        site = OfficialSite.objects.create(entry=entry, url='https://contest.example/',
            evidence_url='https://school.example/notice', allowed_hosts=['contest.example'])
        site.page_attempts = {f'https://contest.example/{i}': i + 1000 for i in range(501)}
        site.page_attempts.update({f'attachment:https://contest.example/{i}.pdf': i for i in range(501)})
        site.save()
        page = Page(site.url, '<title>赛事官网</title><article><p>' + '公开赛事信息与规则。' * 30 + '</p></article>')
        session = SimpleNamespace(get=lambda _site, _url: page)
        sync_site(site, max_pages=1, session=session)
        site.refresh_from_db()
        self.assertEqual(len(site.page_attempts), 1000)
        self.assertIn('attachment:https://contest.example/500.pdf', site.page_attempts)
        self.assertIn('https://contest.example/500', site.page_attempts)
