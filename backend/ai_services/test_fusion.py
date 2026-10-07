from unittest.mock import patch

from django.test import SimpleTestCase

from .chat import chat
from .fusion import fuse, verified_answer_text


def item(kind, url, text, *, version='1', published=None):
    return {'kind': kind, 'entity_id': 'db-1' if kind == 'competition' else '1',
            'version': version, 'title': '机器人创意大赛', 'url': url,
            'internal_url': '/competitions/1' if kind == 'competition' else None,
            'text': text, 'verified_at': '2026-10-04', 'published_on': published,
            'read_at': '2026-10-04', 'status': 'published', 'status_note': '需核实'}


class FusionTests(SimpleTestCase):
    def test_conflicting_versions_keep_dates_and_server_sources(self):
        url = 'https://www.tongji.edu.cn/robot'
        older = item('competition', url, '报名截止是九月。', published='2026-08-01')
        newer = item('web', url, '官网更正为十月。', version=None, published='2026-09-01')
        sources, slots = fuse([older], [], [newer])
        self.assertEqual([source['published_on'] for source in sources], ['2026-08-01', '2026-09-01'])
        self.assertEqual(slots['PLATFORM_CONTEXT'][0]['source_id'], 1)
        self.assertEqual(slots['WEB_CONTEXT'][0]['source_id'], 2)
        self.assertEqual(sources[0]['internal_url'], '/competitions/1')
        self.assertFalse(sources[1]['reviewed'])

    def test_bad_citations_urls_and_duplicate_sources(self):
        url = 'https://www.tongji.edu.cn/robot'
        row = item('competition', url, '实际通知')
        sources, _ = fuse([row, row, item('competition', 'javascript:alert(1)', '错误')], [], [])
        self.assertEqual(len(sources), 1)
        answer = verified_answer_text('依据[1]，另见[88]与 https://evil.example/path。', sources)
        self.assertIn('[1]', answer)
        self.assertNotIn('[88]', answer)
        self.assertNotIn('evil.example', answer)

    def test_no_evidence_does_not_call_model_or_invent_sources(self):
        class Provider:
            def complete_text(self, messages):
                raise AssertionError('no factual source must not call the model')

        with patch('ai_services.chat.retrieve_unified', return_value={
                'records': [], 'knowledge_rows': [], 'knowledge_status': 'no_published_knowledge',
                'mode_used': 'keyword', 'warnings': [],
            }), patch('ai_services.chat.search_external', return_value=([], 'registered_site_not_matched')):
            result = chat([{'role': 'user', 'content': '有哪些机器人比赛'}],
                          client=Provider(), details=True)
        self.assertEqual(result['sources'], [])
        self.assertIn('未查到', result['message']['content'])
        self.assertFalse(result['retrieval']['has_sources'])
