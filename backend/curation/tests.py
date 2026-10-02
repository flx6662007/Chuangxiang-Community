import copy
import hashlib
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase, SimpleTestCase

from competition_catalog.models import CatalogEntry
from competitions.models import Competition
from resources.models import Resource, ResourceRevision
from .models import KnowledgeDocument, DocumentRevision, ImportRun, ImportedObjectRevision, DocumentReview
from .package import load_package, PackageError
from .importer import import_package


def fixture():
    return {
        'schema_version': 1, 'package_id': 'test-tongji',
        'review': {'status': 'approved', 'reviewed_by': 'test', 'reviewed_on': '2026-10-02'},
        'catalog': [{'code': '2026131', 'name': '测试赛事目录', 'grade': 'B', 'levels': '国家级',
                     'departments': ['测试学院'], 'source_url': 'https://example.org/catalog'}],
        'competitions': [{'code': 'curated-example-2025', 'catalog_codes': ['2026131'],
            'fields': {'title': '测试赛事2025', 'edition': '2025年第九届', 'summary': '往届规则',
                       'description': '历史资料，不代表2026报名条件。', 'registration_deadline': '2025-09-01'},
            'sources': [{'source_type': 'official', 'source_name': '测试组委会',
                         'source_url': 'https://example.org/2025', 'is_primary': True}]}],
        'resources': [{'code': 'curated-example-resource', 'catalog_codes': ['2026131'],
            'competition_codes': ['curated-example-2025'],
            'fields': {'title': '公开教程', 'description': '学习方法', 'access_url': 'https://example.org/learn'}}],
        'documents': [{'code': 'curated-example-document', 'title': '往届说明', 'body': '历史正文',
            'edition': '2025年第九届', 'catalog_codes': ['2026131'],
            'competition_codes': ['curated-example-2025'], 'resource_codes': ['curated-example-resource'],
            'sources': [{'url': 'https://example.org/2025', 'locator': '参赛规则'}], 'attachments': []}],
    }


class PackageTests(SimpleTestCase):
    def load(self, data, attachments=None, batches=()):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, body in (attachments or {}).items():
                (root / name).write_bytes(body)
            (root / 'package.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            return load_package(root / 'package.json', batches)

    def test_history_is_not_relabelled_to_catalog_year(self):
        data = self.load(fixture())
        self.assertEqual(data['competitions'][0]['fields']['edition'], '2025年第九届')

    def test_missing_attachment_and_hash_mismatch_are_rejected(self):
        data = fixture()
        data['documents'][0]['attachments'] = [{'path': 'rule.pdf', 'sha256': hashlib.sha256(b'abc').hexdigest()}]
        with self.assertRaises(PackageError):
            self.load(data)
        with self.assertRaises(PackageError):
            self.load(data, {'rule.pdf': b'changed'})
        self.load(data, {'rule.pdf': b'abc'})

    def test_paths_and_hidden_write_fields_are_rejected(self):
        data = fixture()
        data['documents'][0]['attachments'] = [{'path': '../outside.pdf', 'sha256': '0' * 64}]
        with self.assertRaises(PackageError):
            self.load(data)
        data = fixture()
        data['competitions'][0]['fields']['publication_status'] = 'published'
        with self.assertRaises(PackageError):
            self.load(data)

    def test_missing_link_target_is_rejected(self):
        data = fixture()
        data['resources'][0]['competition_codes'] = ['not-present']
        with self.assertRaises(PackageError):
            self.load(data)

    def test_blank_source_name_is_rejected_before_database(self):
        data = fixture()
        data['competitions'][0]['sources'][0]['source_name'] = ' '
        with self.assertRaises(PackageError):
            self.load(data)


class ImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser(email='curator@tongji.edu.cn', password='curation-tests-only-2026')

    def package(self, data=None, batches=()):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'package.json'
            path.write_text(json.dumps(data or fixture(), ensure_ascii=False), encoding='utf-8')
            return load_package(path, batches)

    def test_preview_rolls_back_all_entities(self):
        result = import_package(self.package(), actor=self.actor)
        self.assertEqual(result['document_created'], 1)
        self.assertFalse(Competition.objects.exists())
        self.assertFalse(CatalogEntry.objects.exists())
        self.assertFalse(ImportRun.objects.exists())

    def test_idempotence_drafts_and_actual_edition(self):
        data = self.package()
        import_package(data, actor=self.actor, apply=True)
        before = Competition.objects.get().updated_at
        result = import_package(data, actor=self.actor, apply=True)
        self.assertEqual(result['competition_unchanged'], 1)
        self.assertEqual(Competition.objects.count(), 1)
        self.assertEqual(DocumentRevision.objects.count(), 1)
        self.assertEqual(ResourceRevision.objects.count(), 1)
        event = Competition.objects.get()
        self.assertEqual(event.updated_at, before)
        self.assertEqual(event.edition, '2025年第九届')
        self.assertEqual(event.publication_status, 'draft')
        self.assertFalse(event.recruitment_enabled)
        self.assertEqual(KnowledgeDocument.objects.get().review_status, 'draft')

    def test_updated_document_retains_old_text(self):
        import_package(self.package(), actor=self.actor, apply=True)
        new = fixture()
        new['documents'][0]['body'] = '更正后的历史正文'
        import_package(self.package(new), actor=self.actor, apply=True)
        self.assertEqual(DocumentRevision.objects.count(), 2)
        self.assertEqual(DocumentRevision.objects.get(version=1).body, '历史正文')
        self.assertEqual(KnowledgeDocument.objects.get().current_revision.version, 2)

    def test_offset_deadline_repeat_is_not_a_manual_edit_but_real_change_is(self):
        data = fixture()
        data['competitions'][0]['fields'].update(
            registration_deadline_at='2025-09-01T12:00:00+08:00',
            registration_deadline_timezone='Asia/Shanghai')
        package = self.package(data)
        import_package(package, actor=self.actor, apply=True)
        result = import_package(package, actor=self.actor, apply=True)
        self.assertEqual(result['competition_unchanged'], 1)
        self.assertEqual(ImportedObjectRevision.objects.filter(imported_object__kind='competition').count(), 1)
        from datetime import timedelta
        event = Competition.objects.get()
        event.registration_deadline_at += timedelta(minutes=1)
        event.save(update_fields=['registration_deadline_at'])
        with self.assertRaises(PackageError):
            import_package(package, actor=self.actor, apply=True)

    def test_manual_edit_conflicts_and_rolls_back_earlier_changes(self):
        import_package(self.package(), actor=self.actor, apply=True)
        Resource.objects.update(description='管理员人工修订')
        new = fixture()
        new['competitions'][0]['fields']['summary'] = '拟更新'
        with self.assertRaises(PackageError):
            import_package(self.package(new), actor=self.actor, apply=True)
        self.assertEqual(Competition.objects.get().summary, '往届规则')

    def test_unreviewed_and_nonstaff_cannot_apply(self):
        new = fixture()
        new['review'] = {'status': 'pending'}
        with self.assertRaises(PackageError):
            import_package(self.package(new), actor=self.actor, apply=True)
        actor = get_user_model().objects.create_user(email='student@tongji.edu.cn')
        with self.assertRaises(PermissionDenied):
            import_package(self.package(), actor=actor, apply=True)

    def test_distinct_editions_and_shared_resource(self):
        data = fixture()
        second = copy.deepcopy(data['competitions'][0])
        second['code'] = 'curated-example-2026'
        second['fields']['edition'] = '2026年第十届'
        second['fields']['registration_deadline'] = None
        data['competitions'].append(second)
        data['resources'][0]['competition_codes'].append(second['code'])
        import_package(self.package(data), actor=self.actor, apply=True)
        self.assertEqual(Competition.objects.count(), 2)
        self.assertEqual(Resource.objects.count(), 1)
        self.assertEqual(Resource.objects.get().competitions.count(), 2)

    def test_shared_resource_and_document_fill_links_across_batches(self):
        data = fixture()
        data['catalog'].append({**data['catalog'][0], 'code': '2026156', 'name': '第二批赛事'})
        event = copy.deepcopy(data['competitions'][0])
        event['code'], event['catalog_codes'] = 'curated-second-2025', ['2026156']
        data['competitions'].append(event)
        for kind in ('resources', 'documents'):
            data[kind][0]['catalog_codes'].append('2026156')
            data[kind][0]['competition_codes'].append(event['code'])
        import_package(self.package(data, [1]), actor=self.actor, apply=True)
        import_package(self.package(data, [2]), actor=self.actor, apply=True)
        self.assertEqual(Resource.objects.get().competitions.count(), 2)
        self.assertEqual(ResourceRevision.objects.count(), 2)
        self.assertEqual(KnowledgeDocument.objects.get().current_revision.links.filter(competition__isnull=False).count(), 2)

    def test_omitted_old_deadline_is_cleared_and_relations_are_conflict_checked(self):
        import_package(self.package(), actor=self.actor, apply=True)
        data = fixture()
        del data['competitions'][0]['fields']['registration_deadline']
        import_package(self.package(data), actor=self.actor, apply=True)
        self.assertIsNone(Competition.objects.get().registration_deadline)
        old = ImportedObjectRevision.objects.get(imported_object__kind='competition', version=1)
        self.assertEqual(old.payload['fields']['registration_deadline'], '2025-09-01')
        self.assertEqual(old.state['fields']['registration_deadline'], '2025-09-01')
        Resource.objects.get().competitions.clear()
        with self.assertRaises(PackageError):
            import_package(self.package(data), actor=self.actor, apply=True)

    def test_review_requires_current_version_and_records_audit(self):
        from .services import review_document
        from .retrieval import student_visible_documents
        import_package(self.package(), actor=self.actor, apply=True)
        code = fixture()['documents'][0]['code']
        with self.assertRaises(PackageError):
            review_document(code, revision=2, status='approved', reason='读过旧版本', actor=self.actor)
        self.assertFalse(DocumentReview.objects.exists())
        review_document(code, revision=1, status='approved', reason='已核对历史来源和日期', actor=self.actor)
        self.assertEqual(DocumentReview.objects.count(), 1)
        self.assertEqual(KnowledgeDocument.objects.get().review_status, 'approved')
        self.assertFalse(student_visible_documents().exists())
        review_document(code, revision=1, status='withdrawn', reason='资料需要再次核对', actor=self.actor)
        self.assertEqual(DocumentReview.objects.count(), 2)
        self.assertFalse(student_visible_documents().exists())

    def test_student_retrieval_excludes_unreviewed_and_nonpublic_links(self):
        from .retrieval import student_visible_documents
        import_package(self.package(), actor=self.actor, apply=True)
        self.assertFalse(student_visible_documents().exists())
        KnowledgeDocument.objects.update(review_status='approved')
        self.assertFalse(student_visible_documents().exists())
        # Direct catalog knowledge can be reviewed independently of an edition.
        doc = KnowledgeDocument.objects.get()
        doc.current_revision.links.filter(catalog__isnull=True).delete()
        self.assertTrue(student_visible_documents().exists())
        KnowledgeDocument.objects.update(review_status='withdrawn')
        self.assertFalse(student_visible_documents().exists())
