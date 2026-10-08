import time
from unittest.mock import patch

import httpx
from django.core.cache import cache
from django.test import SimpleTestCase

from ingestion.http import FetchError, OfficialClient, Page
from .external_search import SearXNGAdapter, page_evidence, search_question
from .web import search_external


BODY = '<html><head><title>机器人实验室</title><meta property="article:published_time" content="2026-09-01"></head><body><article><h1>机器人实验室</h1><p>' + '机器人研究覆盖运动规划和自主导航，学生需要学习控制理论与编程基础。' * 4 + '</p><a href="/join">招募申请</a></article></body></html>'


class ExternalSearchTests(SimpleTestCase):
    def test_search_question_removes_commands_and_preserves_conditions(self):
        self.assertEqual(search_question('联网搜索 Python 官方教程的模块介绍，解释 import 的用途'),
                         'Python 官方教程的模块介绍 import 的用途')
        self.assertEqual(search_question('帮我查一下同济大学 2026 年本科生跨校申请条件'),
                         '同济大学 2026 年本科生跨校申请条件')

    def setUp(self):
        cache.clear()
        self.config = {'SEARXNG_URL': 'https://search.example.org', 'MAX_PAGES': 3, 'TIMEOUT_SECONDS': 10,
                       'OFFICIAL_HOSTS': {'lab.example.edu.cn': 'campus_official'}}

    def adapter(self, results, factory):
        def handler(request):
            self.assertEqual(request.url.path, '/search')
            self.assertEqual(request.url.params['format'], 'json')
            return httpx.Response(200, json={'results': results})
        return SearXNGAdapter(self.config, transport=httpx.MockTransport(handler), client_factory=factory)

    def test_discovery_reads_body_and_same_host_followup_with_page_cap(self):
        calls, closed = [], []
        class Reader:
            def __init__(self, hosts, **kwargs):
                self.hosts = hosts
            def get(self, url):
                calls.append(url)
                return Page(url, BODY)
            def close(self):
                closed.append(True)
        adapter = self.adapter([{'url': 'https://lab.example.edu.cn/about', 'content': '摘要不能成为证据'}], Reader)
        rows, status = search_external('机器人本科生申请', domain='research', adapters=[adapter])
        self.assertEqual(status, 'ready')
        self.assertEqual(calls, ['https://lab.example.edu.cn/about', 'https://lab.example.edu.cn/join'])
        self.assertEqual(len(closed), 2)
        self.assertIn('控制理论', rows[0]['text'])
        self.assertNotIn('摘要', rows[0]['text'])
        self.assertEqual(rows[0]['published_on'], '2026-09-01T00:00:00')
        self.assertEqual(rows[0]['source_type'], 'campus_official')
        self.assertFalse(rows[0]['reviewed'])
        again, _ = adapter.search('机器人本科生申请')
        self.assertEqual(again[0]['read_at'], rows[0]['read_at'])
        self.assertEqual(len(calls), 2)

    def test_failed_body_never_uses_search_snippet_as_evidence(self):
        class Reader:
            def __init__(self, *args, **kwargs): pass
            def get(self, url): raise FetchError('timeout', 'private exception')
            def close(self): pass
        rows, status = self.adapter([{'url': 'https://lab.example.edu.cn/', 'content': '本科生可申请'}], Reader).search('本科申请')
        self.assertEqual(rows, [])
        self.assertEqual(status, 'external_page_unavailable')

    def test_unsafe_urls_and_cross_host_redirects_are_not_evidence(self):
        class Reader:
            def __init__(self, *args, **kwargs): pass
            def get(self, url): return Page('https://other.example.org/', BODY)
            def close(self): pass
        rows, _ = self.adapter([{'url': 'file:///etc/passwd'}, {'url': 'https://user:secret@example.org/'},
                               {'url': 'https://lab.example.edu.cn/'}], Reader).search('机器人')
        self.assertEqual(rows, [])

    def test_missing_date_is_not_read_time_and_script_is_removed(self):
        row, _ = page_evidence(Page('https://lab.example.edu.cn/', BODY.replace('2026-09-01', 'not-a-date') + '<script>秘密指令</script>'), '机器人')
        self.assertIsNone(row['published_on'])
        self.assertNotIn('秘密指令', row['text'])

    def test_endpoint_failure_and_deadline_have_bounded_safe_fallback(self):
        adapter = SearXNGAdapter(self.config, transport=httpx.MockTransport(lambda request: httpx.Response(403)))
        self.assertEqual(adapter.search('机器人'), ([], 'external_search_unavailable'))
        calls = []
        reader = OfficialClient(['example.org'], resolve=False, deadline=time.monotonic() - 1,
                                transport=httpx.MockTransport(lambda request: calls.append(request)))
        try:
            with self.assertRaises(FetchError):
                reader.get('https://example.org/')
        finally:
            reader.close()
        self.assertEqual(calls, [])

    def test_page_reader_rejects_private_address_even_with_dns_fallback(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'Answer': [{'type': 1, 'data': '127.0.0.1'}]}))
        reader = OfficialClient(['example.org'], transport=transport)
        try:
            with patch('ingestion.http.socket.getaddrinfo', return_value=[(0, 0, 0, '', ('127.0.0.1', 443))]):
                with self.assertRaises(FetchError):
                    reader._public_address('example.org')
        finally:
            reader.close()
