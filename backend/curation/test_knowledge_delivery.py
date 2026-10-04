"""Full-corpus import, document review, and database retrieval coverage."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from .importer import import_package
from .models import KnowledgeDocument, DocumentRevision
from .package import PackageError, load_package
from .retrieval import student_visible_documents

ROOT = Path(__file__).resolve().parents[2]
IMPORTS = ROOT / 'docs/competition-knowledge-maintenance/imports'


def approved_for_isolated_test(path):
    data = load_package(path)
    data['review'] = {'status': 'approved', 'reviewed_by': 'isolated-test', 'reviewed_on': '2026-10-04'}
    return data


class KnowledgeArtifactsTests(SimpleTestCase):
    def test_packages_cover_corpus_without_parent_files(self):
        corpus = json.loads((ROOT / 'docs/competition-knowledge/corpus.json').read_text(encoding='utf-8'))
        records = {row['id']: row for row in corpus['records']}
        found = {}
        paths = sorted(IMPORTS.glob('import-*.json'))
        self.assertEqual(len(paths), 3)
        for path in paths:
            data = load_package(path)
            scope = path.stem.removeprefix('import-')
            self.assertEqual(data['package_id'], 'competition-knowledge-standalone-v1-' + scope)
            self.assertEqual(data['review']['status'], 'pending')
            self.assertEqual(data['competitions'], [])
            self.assertEqual(data['resources'], [])
            self.assertEqual(data['references'], {'competitions': [], 'resources': []})
            for document in data['documents']:
                row = document['metadata']['search_record']
                self.assertNotIn(row['id'], found)
                self.assertEqual(row, records[row['id']])
                self.assertEqual(document['code'], 'final-' + row['id'])
                self.assertEqual(document['metadata']['corpus_version'], corpus['version'])
                self.assertEqual(document['sources'], row['sources'])
                self.assertEqual(document['body'], '\n\n'.join(
                    f"## {section['heading']}\n\n{section['text']}" for section in row['sections']))
                self.assertEqual(document['attachments'], [])
                self.assertEqual(document['competition_codes'], [])
                self.assertEqual(document['resource_codes'], [])
                found[row['id']] = document
        self.assertEqual(set(found), set(records))

    def test_default_inputs_rebuild_delivered_packages_from_another_directory(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / 'imports'
            result = subprocess.run(
                [sys.executable, str(ROOT / 'scripts/build-knowledge-imports.py'), '--output', str(output)],
                cwd=temporary, capture_output=True, text=True, encoding='utf-8', timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            reports = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([row['documents'] for row in reports], [65, 41, 92])
            self.assertTrue(all(row['edition_dependencies'] == 0 for row in reports))
            expected = sorted(IMPORTS.glob('import-*.json'))
            self.assertEqual([path.name for path in sorted(output.glob('*.json'))],
                             [path.name for path in expected])
            for path in expected:
                self.assertEqual((output / path.name).read_bytes(), path.read_bytes())


class KnowledgeImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser(
            email='knowledge-curator@tongji.edu.cn', password='isolated-knowledge-test')

    def test_full_corpus_import_is_repeatable_and_requires_document_review(self):
        from competitions.models import Competition
        from resources.models import Resource
        from curation.services import review_document
        from information_library.competition_search import database_corpus, search_competitions

        corpus = json.loads((ROOT / 'docs/competition-knowledge/corpus.json').read_text(encoding='utf-8'))
        expected = len(corpus['records'])
        paths = sorted(IMPORTS.glob('import-*.json'))
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
        document = KnowledgeDocument.objects.select_related('current_revision').first()
        review_document(document.code, revision=document.current_revision.version,
                        status='approved', reason='Isolated knowledge retrieval verification', actor=self.actor)
        visible = database_corpus()
        self.assertEqual(len(visible['records']), 1)
        self.assertIsNone(visible['records'][0]['competition_id'])
        result = search_competitions(document.current_revision.title, mode='keyword')
        self.assertEqual(len(result['knowledge_results']), 1)
        self.assertEqual(result['results'], [])
        review_document(document.code, revision=document.current_revision.version,
                        status='withdrawn', reason='Isolated knowledge withdrawal verification', actor=self.actor)
        self.assertEqual(database_corpus()['records'], [])
