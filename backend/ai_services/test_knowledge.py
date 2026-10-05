from hashlib import sha256
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import ProgrammingError
from django.test import TestCase, override_settings
from django.utils import timezone

from competition_catalog.models import CatalogBinding, CatalogEntry
from competitions.models import Competition, CompetitionTaxonomy
from curation.models import DocumentLink, DocumentReview, DocumentRevision, KnowledgeChunk, KnowledgeDocument

from .knowledge import DIMENSION, rebuild_index, retrieve_knowledge


class FakeEncoder:
    """Deterministic fixture for retrieval wiring; never used in production."""

    def encode(self, texts, **kwargs):
        result = []
        for text in texts:
            first = 1.0 if '机器人' in text or 'robot' in text.lower() else 0.0
            second = 1.0 if '算法' in text or 'algorithm' in text.lower() else 0.0
            result.append([first, second] + [0.0] * (DIMENSION - 2))
        return result


class KnowledgeIndexTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(email='ai-index@tongji.edu.cn', password='fixture-only')

    def document(self, status='approved', body='机器人设计课程和 robot design rules。', sources=None):
        doc = KnowledgeDocument.objects.create(code='ai-index-doc', title='机器人指南', review_status='draft')
        revision = DocumentRevision.objects.create(
            document=doc, version=1, title='机器人指南', body=body, edition='2026',
            sources=sources or [{'url': 'https://www.tongji.edu.cn/robot', 'locator': '公开章节'}],
            content_hash=sha256(body.encode()).hexdigest(), created_by=self.actor,
        )
        doc.current_revision = revision
        doc.review_status = status
        doc.save()
        return doc, revision

    def test_empty_index_and_approval_boundary(self):
        self.assertEqual(rebuild_index(), 0)
        self.assertEqual(retrieve_knowledge('机器人')[1], 'no_published_knowledge')
        doc, _ = self.document(status='draft')
        self.assertEqual(rebuild_index(), 0)
        self.assertFalse(KnowledgeChunk.objects.exists())
        doc.review_status = 'approved'
        doc.save()
        self.assertEqual(rebuild_index(encoder=FakeEncoder()), 1)
        self.assertEqual(retrieve_knowledge('机器人', encoder=FakeEncoder())[0][0]['url'],
                         'https://www.tongji.edu.cn/robot')
        doc.review_status = 'withdrawn'
        doc.save()
        self.assertEqual(retrieve_knowledge('robot', encoder=FakeEncoder())[0], [])
        self.assertEqual(rebuild_index(), 0)
        self.assertFalse(KnowledgeChunk.objects.exists())

    def test_direct_publication_is_indexed_without_claiming_verification(self):
        doc, revision = self.document(status='published')
        DocumentReview.objects.create(document=doc, revision=revision, status='published',
                                      actor=self.actor, reason='直接发布')
        self.assertEqual(rebuild_index(encoder=FakeEncoder()), 1)
        rows, status = retrieve_knowledge('机器人', encoder=FakeEncoder())
        self.assertEqual(status, 'ready')
        self.assertEqual(rows[0]['status'], 'published')
        self.assertIsNone(rows[0]['verified_at'])
        self.assertEqual(rows[0]['status_note'], '公开知识资料')

    def test_verified_timestamp_comes_only_from_current_revision_review(self):
        doc, revision = self.document()
        review = DocumentReview.objects.create(document=doc, revision=revision, status='approved',
                                              actor=self.actor, reason='来源核验')
        rebuild_index(encoder=FakeEncoder())
        self.assertEqual(retrieve_knowledge('机器人', encoder=FakeEncoder())[0][0]['verified_at'],
                         review.created_at.isoformat())

    def test_public_documents_without_optional_index_return_unavailable(self):
        self.document(status='published')
        self.assertEqual(retrieve_knowledge('机器人')[1], 'index_unavailable')
        with patch('ai_services.knowledge.KnowledgeChunk.objects.filter',
                   side_effect=ProgrammingError('optional index table absent')):
            self.assertEqual(retrieve_knowledge('机器人'), ([], 'index_unavailable'))
        self.assertEqual(KnowledgeDocument.objects.count(), 1)

    def test_new_revision_and_linked_draft_invalidate_old_vectors(self):
        doc, revision = self.document()
        rebuild_index(encoder=FakeEncoder())
        self.assertTrue(retrieve_knowledge('robot design', encoder=FakeEncoder())[0])
        newer = DocumentRevision.objects.create(
            document=doc, version=2, title='新版本', body='算法新版', edition='2027',
            sources=revision.sources, content_hash=sha256('算法新版'.encode()).hexdigest(), created_by=self.actor)
        doc.current_revision = newer
        doc.save()
        self.assertEqual(retrieve_knowledge('robot', encoder=FakeEncoder())[0], [])
        event = Competition.objects.create(code='ai-index-draft', title='草稿赛事', edition='2027')
        DocumentLink.objects.create(revision=newer, competition=event)
        self.assertEqual(rebuild_index(), 0)
        self.assertEqual(retrieve_knowledge('算法', encoder=FakeEncoder())[0], [])

    def test_chinese_english_and_no_unrelated_hit(self):
        self.document()
        rebuild_index(encoder=FakeEncoder())
        for question in ('机器人规则', 'robot design'):
            self.assertEqual(len(retrieve_knowledge(question, encoder=FakeEncoder())[0]), 1)
        self.assertEqual(retrieve_knowledge('算法', encoder=FakeEncoder())[0], [])

    def test_multiple_source_urls_without_passage_mapping_are_not_indexed(self):
        self.document(sources=[{'url': 'https://www.tongji.edu.cn/robot', 'locator': '公开章节'},
                               {'url': 'https://www.tongji.edu.cn/another', 'locator': '另一章'}])
        self.assertEqual(rebuild_index(encoder=FakeEncoder()), 0)
        self.assertEqual(retrieve_knowledge('机器人', encoder=FakeEncoder())[0], [])

    @override_settings(COMPETITION_CATALOG_ONLY=True)
    def test_linked_published_competition_still_needs_active_catalog_binding(self):
        doc, revision = self.document()
        category = CompetitionTaxonomy.objects.create(code='ai-index-category', kind='category', name='知识测试')
        event = Competition.objects.create(
            code='ai-index-published', title='机器人赛事', edition='2026', summary='公开摘要',
            description='公开说明', category=category, publication_status='published',
            published_at=timezone.now(), last_verified_at=timezone.now(),
        )
        DocumentLink.objects.create(revision=revision, competition=event)
        self.assertEqual(rebuild_index(encoder=FakeEncoder()), 0)
        entry = CatalogEntry.objects.create(code='2026999', name='机器人赛事', grade='A', levels='全国',
                                            source_url='https://www.tongji.edu.cn/catalog')
        CatalogBinding.objects.create(entry=entry, competition=event, basis='测试目录关系')
        self.assertEqual(rebuild_index(encoder=FakeEncoder()), 1)
        entry.is_active = False
        entry.save(update_fields=['is_active'])
        self.assertEqual(retrieve_knowledge('机器人', encoder=FakeEncoder())[0], [])
