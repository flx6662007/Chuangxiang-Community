"""Validate the real delivered corpus through the shared chat retrieval."""
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from curation.knowledge_loader import load_competition_knowledge
from curation.models import KnowledgeDocument, DocumentRevision, DocumentLink, ImportedObject
from curation.retrieval import student_visible_documents
from curation.services import publish_document, review_document
from information_library.competition_search import database_corpus, search_competitions
from information_library.semantic import MODEL_ID, MODEL_REVISION, load_index
from .competition_knowledge import retrieve_knowledge, rebuild_index


class FixtureEncoder:
    model_id, revision = MODEL_ID, MODEL_REVISION

    def encode(self, texts, **kwargs):
        import numpy as np
        # Used solely to check indexing coverage/version contracts, not relevance.
        return np.array([[1., float('工程' in text), float('英语' in text)] for text in texts])


class UnifiedKnowledgeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser('guide-curator@tongji.edu.cn', 'isolated-guide-password')
        load_competition_knowledge(actor=cls.actor, reason='隔离库验收', apply=True)

    def test_all_198_documents_including_multiple_sources_are_indexed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'knowledge.npz'
            rebuild_index(path=path, encoder=FixtureEncoder())
            index = load_index(path, encoder=FixtureEncoder())
            self.assertEqual(len(index.metadata['record_hashes']), 198)
            self.assertEqual(len({chunk['record_id'] for chunk in index.metadata['chunks']}), 198)

    def test_chat_quotes_supported_passages_from_multi_source_document(self):
        with patch.dict('os.environ', {'COMPETITION_SEMANTIC_INDEX': ''}):
            rows, status = retrieve_knowledge('全国大学生工程实践与创新能力大赛')
        self.assertEqual(status, 'ready')
        self.assertTrue(rows)
        for row in rows:
            self.assertTrue(row['url'].startswith('https://'))
            self.assertTrue(row['text'])

    def test_direct_publication_remains_searchable_and_idempotent(self):
        doc = KnowledgeDocument.objects.get(code='final-m89-2026001-overview')
        review_document(doc.code, revision=doc.current_revision.version, status='draft', reason='状态测试', actor=self.actor)
        publish_document(doc.code, actor=self.actor)
        result = load_competition_knowledge(actor=self.actor, reason='重复导入', apply=True)
        self.assertEqual(result['searchable_documents'], 198)
        self.assertEqual(result['counts']['documents_created'], 0)
        self.assertTrue(search_competitions('中国国际大学生创新大赛', mode='keyword')['hits'])

    def test_withdrawal_and_changed_body_stop_returning_document(self):
        doc = KnowledgeDocument.objects.get(code='final-m89-2026001-overview')
        doc.current_revision.body += '\n不同于证据映射的文字'
        doc.current_revision.save(update_fields=['body'])
        self.assertNotIn('m89-2026001-overview', {r['id'] for r in database_corpus()['records']})
        review_document(doc.code, revision=doc.current_revision.version, status='withdrawn', reason='撤下测试', actor=self.actor)
        self.assertEqual(len(database_corpus()['records']), 197)

    def test_legacy_copy_does_not_reappear_when_replacement_is_withdrawn(self):
        replacement = KnowledgeDocument.objects.get(code='final-m89-2026001-overview')
        source = replacement.current_revision
        legacy = KnowledgeDocument.objects.create(code='legacy-copy', title=source.title)
        revision = DocumentRevision.objects.create(document=legacy, version=1,
            title=source.title, body=source.body, edition=source.edition,
            sources=source.sources, content_hash=source.content_hash, created_by=self.actor)
        DocumentLink.objects.create(revision=revision, catalog=source.links.get().catalog)
        legacy.current_revision = revision
        legacy.review_status = 'published'
        legacy.save()
        ImportedObject.objects.create(kind='document', code=legacy.code,
            package_id='tongji-2026-001-089', payload_hash='a' * 64, state_hash='b' * 64)
        self.assertFalse(student_visible_documents().filter(pk=legacy.pk).exists())
        review_document(replacement.code, revision=source.version, status='withdrawn',
                        reason='withdrawal regression', actor=self.actor)
        self.assertFalse(student_visible_documents().filter(pk__in=[legacy.pk, replacement.pk]).exists())
