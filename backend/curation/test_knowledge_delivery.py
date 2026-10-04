"""Integration coverage for the product corpus and compatible import overlays."""
import json
import os
from pathlib import Path
import unittest

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from .importer import import_package
from .models import KnowledgeDocument, DocumentRevision
from .package import PackageError, load_package
from .retrieval import student_visible_documents

ROOT = Path(__file__).resolve().parents[2]
IMPORTS = ROOT / 'docs/competition-knowledge-maintenance/imports'
STANDALONE_IMPORTS = ROOT / 'docs/competition-knowledge-maintenance/standalone-imports'


def approved_for_isolated_test(path):
    data = load_package(path)
    data['review'] = {'status': 'approved', 'reviewed_by': 'isolated-test', 'reviewed_on': '2026-10-04'}
    return data


class KnowledgeArtifactsTests(SimpleTestCase):
    def test_overlays_cover_corpus_without_publishing_business_objects(self):
        corpus = json.loads((ROOT / 'docs/competition-knowledge/corpus.json').read_text(encoding='utf-8'))
        records = {row['id']: row for row in corpus['records']}
        found = {}
        for path in sorted(IMPORTS.glob('import-*.json')):
            data = load_package(path)
            self.assertEqual(data['review']['status'], 'pending')
            self.assertEqual(data['competitions'], [])
            self.assertEqual(data['resources'], [])
            for document in data['documents']:
                row = document['metadata']['search_record']
                self.assertNotIn(row['id'], found)
                self.assertEqual(row, records[row['id']])
                self.assertEqual(document['metadata']['corpus_version'], corpus['version'])
                self.assertEqual(document['sources'], row['sources'])
                found[row['id']] = document
        self.assertEqual(set(found), set(records))

    def test_standalone_packages_cover_corpus_without_parent_files(self):
        corpus = json.loads((ROOT / 'docs/competition-knowledge/corpus.json').read_text(encoding='utf-8'))
        records = {row['id']: row for row in corpus['records']}
        found = {}
        paths = sorted(STANDALONE_IMPORTS.glob('import-*.json'))
        self.assertEqual(len(paths), 3)
        for path in paths:
            data = load_package(path)
            linked = load_package(IMPORTS / path.name)
            self.assertNotEqual(data['package_id'], linked['package_id'])
            self.assertEqual(data['review']['status'], 'pending')
            self.assertEqual(data['competitions'], [])
            self.assertEqual(data['resources'], [])
            self.assertEqual(data['references'], {'competitions': [], 'resources': []})
            self.assertEqual({row['code'] for row in data['documents']},
                             {row['code'] for row in linked['documents']})
            for document in data['documents']:
                row = document['metadata']['search_record']
                self.assertNotIn(row['id'], found)
                self.assertEqual(row, records[row['id']])
                self.assertEqual(document['metadata']['corpus_version'], corpus['version'])
                self.assertEqual(document['sources'], row['sources'])
                self.assertEqual(document['attachments'], [])
                self.assertEqual(document['competition_codes'], [])
                self.assertEqual(document['resource_codes'], [])
                found[row['id']] = document
        self.assertEqual(set(found), set(records))


class StandaloneKnowledgeImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser(
            email='standalone-curator@tongji.edu.cn', password='isolated-knowledge-test')

    def test_full_corpus_import_is_repeatable_and_requires_document_review(self):
        from competitions.models import Competition
        from resources.models import Resource
        from curation.services import review_document
        from information_library.competition_search import database_corpus, search_competitions

        corpus = json.loads((ROOT / 'docs/competition-knowledge/corpus.json').read_text(encoding='utf-8'))
        expected = len(corpus['records'])
        paths = sorted(STANDALONE_IMPORTS.glob('import-*.json'))
        self.assertEqual(len(paths), 3)
        with self.assertRaisesMessage(PackageError, '资料包尚未审核'):
            import_package(load_package(paths[0]), actor=self.actor, apply=True)
        self.assertFalse(KnowledgeDocument.objects.exists())
        for path in paths:
            data = approved_for_isolated_test(path)
            before = KnowledgeDocument.objects.count()
            preview = import_package(data, actor=self.actor)
            self.assertEqual(preview['document_created'], len(data['documents']))
            self.assertEqual(KnowledgeDocument.objects.count(), before)
            applied = import_package(data, actor=self.actor, apply=True)
            self.assertEqual(applied['document_created'], len(data['documents']))
            repeated = import_package(data, actor=self.actor, apply=True)
            self.assertEqual(repeated['document_unchanged'], len(data['documents']))
        self.assertEqual(KnowledgeDocument.objects.count(), expected)
        self.assertEqual(DocumentRevision.objects.count(), expected)
        self.assertEqual(KnowledgeDocument.objects.filter(review_status='draft').count(), expected)
        self.assertFalse(Competition.objects.exists())
        self.assertFalse(Resource.objects.exists())
        self.assertFalse(student_visible_documents().exists())
        with self.assertRaisesMessage(PackageError, '已存在但不属于本资料包'):
            import_package(approved_for_isolated_test(IMPORTS / 'import-001-089.json'),
                           actor=self.actor, apply=True)
        self.assertEqual(KnowledgeDocument.objects.count(), expected)
        self.assertEqual(DocumentRevision.objects.count(), expected)
        document = KnowledgeDocument.objects.select_related('current_revision').first()
        review_document(document.code, revision=document.current_revision.version,
                        status='approved', reason='Isolated standalone retrieval verification', actor=self.actor)
        visible = database_corpus()
        self.assertEqual(len(visible['records']), 1)
        self.assertIsNone(visible['records'][0]['competition_id'])
        result = search_competitions(document.current_revision.title, mode='keyword')
        self.assertEqual(len(result['knowledge_results']), 1)
        self.assertEqual(result['results'], [])
        review_document(document.code, revision=document.current_revision.version,
                        status='withdrawn', reason='Isolated standalone withdrawal verification', actor=self.actor)
        self.assertEqual(database_corpus()['records'], [])

    def test_existing_linked_documents_block_standalone_mode(self):
        linked = approved_for_isolated_test(IMPORTS / 'import-001-089.json')
        import_package(linked, actor=self.actor, apply=True)
        before = DocumentRevision.objects.count()
        with self.assertRaisesMessage(PackageError, '已存在但不属于本资料包'):
            import_package(approved_for_isolated_test(STANDALONE_IMPORTS / 'import-001-089.json'),
                           actor=self.actor, apply=True)
        self.assertEqual(DocumentRevision.objects.count(), before)
        self.assertFalse(student_visible_documents().exists())


class KnowledgeOverlayImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser(
            email='knowledge-curator@tongji.edu.cn', password='isolated-knowledge-test')

    def test_overview_preview_and_idempotent_import_keep_review_boundary(self):
        data = approved_for_isolated_test(IMPORTS / 'import-001-089.json')
        expected = len(data['documents'])
        self.assertGreater(expected, 0)
        preview = import_package(data, actor=self.actor)
        self.assertEqual(preview['document_created'], expected)
        self.assertFalse(KnowledgeDocument.objects.exists())
        import_package(data, actor=self.actor, apply=True)
        repeated = import_package(data, actor=self.actor, apply=True)
        self.assertEqual(repeated['document_unchanged'], expected)
        self.assertEqual(DocumentRevision.objects.count(), expected)
        self.assertFalse(student_visible_documents().exists())
        for doc in KnowledgeDocument.objects.select_related('current_revision'):
            self.assertEqual(doc.review_status, 'draft')
            self.assertEqual(doc.current_revision.metadata['search_record']['competition_id'], None)
        from curation.services import review_document
        from information_library.competition_search import database_corpus, search_competitions
        document = KnowledgeDocument.objects.select_related('current_revision').first()
        review_document(document.code, revision=document.current_revision.version,
                        status='approved', reason='Isolated retrieval verification', actor=self.actor)
        published_corpus = database_corpus()
        self.assertEqual(len(published_corpus['records']), 1)
        result = search_competitions(document.current_revision.title, mode='keyword')
        self.assertEqual(len(result['knowledge_results']), 1)
        self.assertEqual(result['results'], [])
        review_document(document.code, revision=document.current_revision.version,
                        status='withdrawn', reason='Isolated withdrawal verification', actor=self.actor)
        self.assertEqual(database_corpus()['records'], [])

    @unittest.skipUnless(os.getenv('KNOWLEDGE_DELIVERY_PACKAGE_131') and os.getenv('KNOWLEDGE_DELIVERY_PACKAGE_90'),
                         'Full original packages are explicitly supplied for integration coverage.')
    def test_all_real_packages_and_overlays_are_repeatable_in_isolated_database(self):
        for path in [os.environ['KNOWLEDGE_DELIVERY_PACKAGE_131'], os.environ['KNOWLEDGE_DELIVERY_PACKAGE_90'],
                     ROOT / 'docs/competition-research/tongji-2026-001-089/导入清单.json']:
            import_package(approved_for_isolated_test(path), actor=self.actor, apply=True)
        baseline = DocumentRevision.objects.count()
        expected = 0
        for path in sorted(IMPORTS.glob('import-*.json')):
            data = approved_for_isolated_test(path)
            expected += len(data['documents'])
            preview = import_package(data, actor=self.actor)
            self.assertEqual(preview['document_created'], len(data['documents']))
            import_package(data, actor=self.actor, apply=True)
            repeated = import_package(data, actor=self.actor, apply=True)
            self.assertEqual(repeated['document_unchanged'], len(data['documents']))
        self.assertEqual(DocumentRevision.objects.count(), baseline + expected)
        self.assertFalse(student_visible_documents().exists())
