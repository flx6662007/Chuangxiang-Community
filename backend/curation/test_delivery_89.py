"""前 89 项资料包：范围、离线校验与隔离入库，不访问开发数据库。"""
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from competition_catalog.models import CatalogEntry
from competitions.models import Competition
from resources.models import Resource, ResourceRevision
from .importer import import_package
from .models import DocumentRevision, ImportRun, KnowledgeDocument
from .package import PackageError, load_package
from .retrieval import student_visible_documents
from .tests import fixture


def summary_fixture():
    data = {
        'schema_version': 1, 'package_id': 'test-tongji-001-089',
        'catalog_scope': {'first': 1, 'last': 89, 'batch_size': 25},
        'review': {'status': 'approved', 'reviewed_by': 'isolated-test', 'reviewed_on': '2026-10-03'},
        'catalog': [], 'competitions': [], 'resources': [], 'documents': [],
    }
    for number in range(1, 90):
        code = f'2026{number:03}'
        resource_code = f'test-resource-{number:03}'
        data['catalog'].append({
            'code': code, 'name': f'测试目录 {number}', 'grade': 'A', 'levels': '国家级',
            'departments': ['测试学院'], 'source_url': 'https://example.org/catalog',
        })
        data['resources'].append({
            'code': resource_code, 'catalog_codes': [code], 'competition_codes': [],
            'fields': {'title': f'学习资源 {number}', 'description': '仅有索引入口，附件尚未阅读。',
                       'access_url': f'https://example.org/resources/{number}'},
        })
        data['documents'].append({
            'code': f'test-summary-{number:03}', 'title': f'资料摘要 {number}',
            'body': '人工摘要与来源；不是网页全文，也不代表当前报名通知。',
            'edition': '多届资料', 'catalog_codes': [code], 'competition_codes': [],
            'resource_codes': [resource_code], 'sources': [{'url': f'https://example.org/{number}'}],
            'metadata': {'edition_note': '往届规则仅作学习用途', 'verified_by': 'official_index',
                         'catalog_correspondence': 'pending', 'checked_on': '2026-10-03'},
        })
    return data


class PackageScopeTests(SimpleTestCase):
    def load(self, data, batches=()):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'package.json'
            path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            return load_package(path, batches)

    def test_new_scope_has_four_exact_batches(self):
        data = summary_fixture()
        self.assertEqual(self.load(data)['_batch_numbers'], [1, 2, 3, 4])
        for batch, first, last in [(1, 1, 25), (2, 26, 50), (3, 51, 75), (4, 76, 89)]:
            with self.subTest(batch=batch):
                selected = self.load(data, [batch])
                self.assertEqual([r['code'] for r in selected['catalog']],
                                 [f'2026{n:03}' for n in range(first, last + 1)])
                self.assertEqual(len(selected['documents']), last - first + 1)
                self.assertEqual(len(selected['resources']), last - first + 1)
        self.assertEqual(len(self.load(data, [2, 4])['catalog']), 39)

    def test_legacy_default_retains_five_batches(self):
        data = fixture()
        original = data['catalog'][0]
        data['catalog'] = [{**original, 'code': f'2026{n}'} for n in range(131, 256)]
        self.assertEqual(self.load(data)['_batch_numbers'], [1, 2, 3, 4, 5])
        for batch in range(1, 6):
            first = 131 + (batch - 1) * 25
            selected = self.load(data, [batch])
            self.assertEqual([r['code'] for r in selected['catalog']],
                             [f'2026{n}' for n in range(first, first + 25)])

    def test_unsupported_scope_and_out_of_scope_catalog_are_rejected(self):
        scope = summary_fixture()['catalog_scope']
        for value in [None, [], {}, {**scope, 'last': 90}, {**scope, 'first': True},
                      {**scope, 'batch_size': 1}, {**scope, 'first': '1'},
                      {**scope, 'extra': 1}, {'first': 131, 'last': 255, 'batch_size': 25}]:
            with self.subTest(scope=value), self.assertRaises(PackageError):
                self.load({**summary_fixture(), 'catalog_scope': value})
        for code in ['2026000', '2026090', '2026131', '2025001', '20261']:
            data = summary_fixture()
            data['catalog'][0]['code'] = code
            with self.subTest(code=code), self.assertRaises(PackageError):
                self.load(data)
        data = summary_fixture()
        del data['catalog_scope']
        with self.assertRaises(PackageError):
            self.load(data)

    def test_invalid_batch_cannot_hide_alongside_valid_batch(self):
        for batches in [[0], [-1], [5], [1, 5], [True], ['1'], [1.0], None]:
            with self.subTest(batches=batches), self.assertRaises(PackageError):
                self.load(summary_fixture(), batches)
        with self.assertRaises(PackageError):
            self.load(fixture(), [1, 6])

    def test_read_only_command_needs_no_database_or_actor(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'package.json'
            path.write_text(json.dumps(summary_fixture()), encoding='utf-8')
            output = io.StringIO()
            call_command('import_curated_competitions', str(path), batch=[4], stdout=output)
            result = json.loads(output.getvalue())
            self.assertEqual(result['mode'], 'validate')
            self.assertEqual(result['counts'], {'catalog': 14, 'competitions': 0,
                                               'resources': 14, 'documents': 14})
            self.assertEqual(result['available_batches'], [1, 2, 3, 4])


class SummaryImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser(
            email='summary-test@tongji.edu.cn', password='isolated-test-only')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'package.json'
        self.path.write_text(json.dumps(summary_fixture()), encoding='utf-8')

    def test_four_batches_repeat_preserve_metadata_and_unpublished_state(self):
        full = load_package(self.path)
        for repeat in range(2):
            for batch in full['_batch_numbers']:
                result = import_package(load_package(self.path, [batch]), actor=self.actor, apply=True)
                if repeat:
                    self.assertEqual(result.get('document_created', 0), 0)
                    self.assertEqual(result.get('resource_created', 0), 0)
        self.assertEqual(CatalogEntry.objects.count(), 89)
        self.assertEqual(Resource.objects.count(), 89)
        self.assertEqual(KnowledgeDocument.objects.count(), 89)
        self.assertEqual(DocumentRevision.objects.count(), 89)
        self.assertEqual(ResourceRevision.objects.count(), 89)
        self.assertFalse(Competition.objects.exists())
        self.assertFalse(Resource.objects.exclude(publication_status='draft').exists())
        self.assertFalse(KnowledgeDocument.objects.exclude(review_status='draft').exists())
        self.assertFalse(student_visible_documents().exists())
        revision = DocumentRevision.objects.first()
        self.assertEqual(revision.edition, '多届资料')
        self.assertEqual(revision.metadata['verified_by'], 'official_index')
        self.assertEqual(revision.metadata['catalog_correspondence'], 'pending')
        self.assertTrue(revision.links.filter(catalog__isnull=False).exists())
        self.assertTrue(revision.links.filter(resource__isnull=False).exists())

    def test_preview_and_permission_boundary_are_unchanged(self):
        data = load_package(self.path, [1])
        import_package(data, actor=self.actor)
        self.assertFalse(CatalogEntry.objects.exists())
        self.assertFalse(Resource.objects.exists())
        self.assertFalse(KnowledgeDocument.objects.exists())
        self.assertFalse(ImportRun.objects.exists())
        staff = get_user_model().objects.create_user(email='limited-staff@tongji.edu.cn', is_staff=True)
        with self.assertRaises(PermissionDenied):
            import_package(data, actor=staff, apply=True)
        data['review'] = {'status': 'pending'}
        with self.assertRaises(PackageError):
            import_package(data, actor=self.actor, apply=True)
        self.assertFalse(CatalogEntry.objects.exists())


@unittest.skipUnless(os.environ.get('CURATION_TEST_PACKAGE_89'), '未指定前 89 项真实交付包')
class Delivery89Tests(TestCase):
    def test_real_package_four_batches_repeat_and_draft_only(self):
        path = Path(os.environ['CURATION_TEST_PACKAGE_89'])
        full = load_package(path)
        self.assertEqual(len(full['catalog']), 89)
        self.assertEqual(full['_batch_numbers'], [1, 2, 3, 4])
        self.assertEqual(full['competitions'], [])
        actor = get_user_model().objects.create_superuser(
            email='delivery89-test@tongji.edu.cn', password='isolated-test-only')
        for repeat in range(2):
            for batch in full['_batch_numbers']:
                data = copy.deepcopy(load_package(path, [batch]))
                data['review'] = {'status': 'approved', 'reviewed_by': 'isolated-test-fixture',
                                  'reviewed_on': '2026-10-03'}
                import_package(data, actor=actor, apply=True)
            if not repeat:
                revisions_before = DocumentRevision.objects.count()
                resource_revisions_before = ResourceRevision.objects.count()
        self.assertEqual(CatalogEntry.objects.count(), 89)
        self.assertFalse(Competition.objects.exists())
        self.assertEqual(Resource.objects.count(), len(full['resources']))
        self.assertEqual(KnowledgeDocument.objects.count(), len(full['documents']))
        self.assertEqual(DocumentRevision.objects.count(), revisions_before)
        self.assertEqual(ResourceRevision.objects.count(), resource_revisions_before)
        self.assertFalse(Resource.objects.exclude(publication_status='draft').exists())
        self.assertFalse(KnowledgeDocument.objects.exclude(review_status='draft').exists())
        self.assertFalse(student_visible_documents().exists())
        for row in full['documents']:
            revision = KnowledgeDocument.objects.get(code=row['code']).current_revision
            self.assertEqual(revision.edition, row.get('edition', ''))
            for key, value in row.get('metadata', {}).items():
                self.assertEqual(revision.metadata[key], value)
