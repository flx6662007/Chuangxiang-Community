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

    def test_catalog_association_is_searchable_and_changes_invalidate_index(self):
        records = self.records()
        records[1]['catalogs'] = [{'code': 'catalog-1', 'name': '编程竞赛', 'aliases': ['Python 竞赛']}]
        records[1]['named_associations'] = [{'object_id': 'db-1', 'title': '编程竞赛本届'}]
        index = build_index(records, encoder=FakeEncoder())
        hits = search(records, 'Python 竞赛', index=index, encoder=FakeEncoder())
        self.assertIn(('resource', 'robot'), hits)
        for key in ('catalogs', 'named_associations'):
            changed = [dict(row) for row in records]
            changed[1][key] = []
            with self.subTest(key=key), self.assertRaisesMessage(SemanticError, 'unified_index_stale'):
                search(changed, 'Python 竞赛', index=index, encoder=FakeEncoder())

    def test_previous_index_schema_requires_rebuild(self):
        records = self.records()
        index = build_index(records, encoder=FakeEncoder())
        index['metadata']['schema_version'] = 2
        with self.assertRaisesMessage(SemanticError, 'unified_index_stale'):
            search(records, 'Python 入门', index=index, encoder=FakeEncoder())
