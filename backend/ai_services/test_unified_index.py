"""Offline BGE-index plumbing with deterministic test embeddings."""

from django.test import SimpleTestCase

from information_library.semantic import SemanticError

from .unified_index import build_index, search


class FakeEncoder:
    model_id = 'test-bge'
    revision = 'test-revision'

    def encode(self, texts, *, is_query=False):
        return [[1.0, 0.0] if 'Python' in text else [0.0, 1.0] for text in texts]


class UnifiedIndexTests(SimpleTestCase):
    def records(self):
        return [{
            'object_type': 'resource', 'object_id': code, 'version': '1', 'status': 'published',
            'title': title, 'summary': summary, 'content': summary, 'tags': [],
            'category': '课程', 'direction': [], 'source_url': f'https://www.tongji.edu.cn/{code}',
        } for code, title, summary in [('python', 'Python 入门', '学习 Python 编程'),
                                       ('robot', '机器人控制', '控制基础')]]

    def test_index_search_and_stale_content_rejection(self):
        records = self.records()
        index = build_index(records, encoder=FakeEncoder())
        hits = search(records, 'Python 入门', index=index, encoder=FakeEncoder())
        self.assertEqual(set(hits), {('resource', 'python')})
        records[0]['summary'] = '内容已更新'
        with self.assertRaisesMessage(SemanticError, 'unified_index_stale'):
            search(records, 'Python 入门', index=index, encoder=FakeEncoder())
