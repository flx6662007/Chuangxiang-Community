"""The independent release can be loaded, searched, updated and repeated."""
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from competition_catalog.models import CatalogEntry
from competitions.models import Competition
from resources.models import Resource
from information_library.competition_search import database_corpus, search_competitions
from .importer import import_package
from .knowledge_loader import (DEFAULT_DIRECTORY, PACKAGE_RANGES, load_competition_knowledge,
                               load_knowledge_packages)
from .models import DocumentReview, DocumentRevision, ImportedObject, ImportRun, KnowledgeDocument
from .package import PackageError, digest
from .services import review_document


def read_packages():
    return [json.loads((DEFAULT_DIRECTORY / f'import-{scope}.json').read_text(encoding='utf-8'))
            for scope in PACKAGE_RANGES]


def write_packages(directory, packages):
    records = []
    for package in packages:
        for row in package['documents']:
            record = row['metadata']['search_record']
            record['content_hash'] = digest({key: value for key, value in record.items() if key != 'content_hash'})
            row['body'] = '\n\n'.join(f"## {section['heading']}\n\n{section['text']}" for section in record['sections'])
            records.append(record)
    version = digest(records)[:16]
    for scope, package in zip(PACKAGE_RANGES, packages):
        package['corpus_version'] = version
        for row in package['documents']:
            row['metadata']['corpus_version'] = version
        (directory / f'import-{scope}.json').write_text(json.dumps(package, ensure_ascii=False), encoding='utf-8')


class KnowledgeLoaderPackageTests(SimpleTestCase):
    def test_delivered_three_packages_form_one_complete_corpus(self):
        packages, version = load_knowledge_packages()
        self.assertEqual(len(packages), 3)
        self.assertEqual(sum(len(package['documents']) for package in packages), 198)
        corpus = json.loads((DEFAULT_DIRECTORY.parents[1] / 'competition-knowledge/corpus.json').read_text(encoding='utf-8'))
        self.assertEqual(version, corpus['version'])

    def test_rejects_a_business_dependency_and_inconsistent_search_text(self):
        for change in ('dependency', 'body', 'source', 'version', 'evidence'):
            with self.subTest(change=change), TemporaryDirectory() as folder:
                directory = Path(folder)
                packages = read_packages()
                write_packages(directory, packages)
                first = directory / 'import-001-089.json'
                data = json.loads(first.read_text(encoding='utf-8'))
                row = data['documents'][0]
                if change == 'dependency':
                    row['metadata']['search_record']['competition_id'] = 123
                elif change == 'body':
                    row['body'] += '\n变更正文'
                elif change == 'source':
                    row['sources'] = [{**row['sources'][0], 'url': 'https://example.org/other'}]
                elif change == 'version':
                    data['corpus_version'] = 'other-version'
                else:
                    record = row['metadata']['search_record']
                    record['sections'][0]['evidence_ids'] = ['missing-source']
                    record['content_hash'] = digest({key: value for key, value in record.items() if key != 'content_hash'})
                first.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
                with self.assertRaises((PackageError, ValueError)):
                    load_knowledge_packages(directory)


class KnowledgeLoaderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser(
            email='batch-knowledge-curator@tongji.edu.cn', password='isolated-knowledge-test')

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.packages = read_packages()
        for package in self.packages:
            package['documents'] = package['documents'][:1]
        write_packages(self.directory, self.packages)
        self.reason = '审核赛事成品正文、参赛字段及来源，启用本批知识。'

    def load(self, **kwargs):
        return load_competition_knowledge(actor=self.actor, reason=self.reason,
                                         directory=self.directory, **kwargs)

    def test_full_release_is_immediately_searchable_repeatable_and_preserves_old_data(self):
        old = KnowledgeDocument.objects.create(code='legacy-directory-notes', title='旧目录资料')
        old_state = (old.title, old.review_status, old.current_revision_id)
        report = load_competition_knowledge(actor=self.actor, reason=self.reason, apply=True)
        self.assertEqual(report['documents'], 198)
        self.assertEqual(report['searchable_documents'], 198)
        self.assertEqual(report['counts']['documents_created'], 198)
        self.assertEqual(report['counts']['documents_reviewed'], 198)
        before = (DocumentRevision.objects.count(), DocumentReview.objects.count(), ImportRun.objects.count())
        row = self.packages[0]['documents'][0]['metadata']['search_record']
        result = search_competitions(row['title'], mode='keyword', limit=50)
        self.assertIn(row['id'], {hit['record_id'] for hit in result['knowledge_results']})
        self.assertEqual(result['results'], [])
        repeated = load_competition_knowledge(actor=self.actor, reason=self.reason, apply=True)
        self.assertEqual(repeated['counts']['documents_unchanged'], 198)
        self.assertEqual(repeated['counts']['documents_reviewed'], 0)
        self.assertEqual(before, (DocumentRevision.objects.count(), DocumentReview.objects.count(), ImportRun.objects.count()))
        self.assertEqual(KnowledgeDocument.objects.filter(code__startswith='final-').count(), 198)
        self.assertEqual(Resource.objects.filter(publication_status='published').count(), 302)
        self.assertTrue(Competition.objects.filter(recruitment_enabled=True).exists())
        old.refresh_from_db()
        self.assertEqual((old.title, old.review_status, old.current_revision_id), old_state)

    def test_default_preview_runs_approval_and_rolls_back_everything(self):
        report = self.load()
        self.assertEqual(report['mode'], 'preview-rolled-back')
        self.assertEqual(report['searchable_documents'], 3)
        for model in (KnowledgeDocument, DocumentRevision, DocumentReview, ImportedObject, ImportRun, CatalogEntry):
            self.assertFalse(model.objects.exists(), model.__name__)
        self.assertEqual(database_corpus()['records'], [])

    def test_failure_in_second_package_rolls_back_the_first(self):
        def fail_second(data, **kwargs):
            if data['package_id'].endswith('090-130'):
                raise PackageError('第二包测试失败')
            return import_package(data, **kwargs)

        with patch('curation.knowledge_loader.import_package', side_effect=fail_second):
            with self.assertRaisesMessage(PackageError, '第二包测试失败'):
                self.load(apply=True)
        for model in (KnowledgeDocument, DocumentRevision, DocumentReview, ImportedObject, ImportRun, CatalogEntry):
            self.assertFalse(model.objects.exists(), model.__name__)

    def test_loader_requires_import_and_review_permissions_and_a_reason(self):
        staff = get_user_model().objects.create_user(email='batch-staff@tongji.edu.cn', password='isolated-knowledge-test', is_staff=True)
        with self.assertRaises(PermissionDenied):
            load_competition_knowledge(actor=staff, reason=self.reason, directory=self.directory, apply=True)
        permissions = ['add_importrun', 'add_knowledgedocument', 'add_competition', 'change_competition',
                       'add_competitionsource', 'add_resource', 'change_resource']
        staff.user_permissions.add(*Permission.objects.filter(codename__in=permissions))
        staff = get_user_model().objects.get(pk=staff.pk)
        with self.assertRaisesMessage(PermissionDenied, '审核权限'):
            load_competition_knowledge(actor=staff, reason=self.reason, directory=self.directory, apply=True)
        with self.assertRaises(PackageError):
            load_competition_knowledge(actor=self.actor, reason='', directory=self.directory, apply=True)
        self.assertFalse(KnowledgeDocument.objects.exists())

    def test_update_creates_reviewed_versions_and_keeps_previous_revisions(self):
        self.load(apply=True)
        first = self.packages[0]['documents'][0]
        document = KnowledgeDocument.objects.get(code=first['code'])
        old_revision = document.current_revision
        first['metadata']['search_record']['sections'][0]['text'] += '\n作品主题包含算法设计。'
        write_packages(self.directory, self.packages)
        report = self.load(apply=True)
        self.assertEqual(report['counts']['documents_updated'], 3)
        document.refresh_from_db()
        self.assertEqual(document.review_status, 'approved')
        self.assertEqual(document.current_revision.version, 2)
        self.assertIn('算法设计', document.current_revision.body)
        self.assertEqual(DocumentRevision.objects.get(pk=old_revision.pk).body, old_revision.body)
        self.assertEqual(self.load(apply=True)['counts']['documents_reviewed'], 0)

    def test_withdrawn_document_stays_withdrawn_on_repeat(self):
        self.load(apply=True)
        document = KnowledgeDocument.objects.get(code=self.packages[0]['documents'][0]['code'])
        review_document(document.code, revision=document.current_revision.version, status='withdrawn',
                        reason='撤下此条知识', actor=self.actor)
        reviews = DocumentReview.objects.count()
        report = self.load(apply=True)
        document.refresh_from_db()
        self.assertEqual(document.review_status, 'withdrawn')
        self.assertEqual(report['counts']['documents_withdrawn'], 1)
        self.assertEqual(report['searchable_documents'], 2)
        self.assertEqual(DocumentReview.objects.count(), reviews)

    def test_removed_release_record_is_retired_and_history_and_old_data_remain(self):
        legacy = KnowledgeDocument.objects.create(code='old-catalog-background', title='原目录背景')
        extra = deepcopy(read_packages()[0]['documents'][1])
        self.packages[0]['documents'].append(extra)
        write_packages(self.directory, self.packages)
        self.assertEqual(self.load(apply=True)['searchable_documents'], 4)
        removed = KnowledgeDocument.objects.get(code=extra['code'])
        revision_id = removed.current_revision_id
        original_body = removed.current_revision.body
        self.packages[0]['documents'].pop()
        write_packages(self.directory, self.packages)
        preview = self.load()
        self.assertEqual(preview['counts']['documents_retired'], 1)
        removed.refresh_from_db()
        self.assertEqual(removed.review_status, 'approved')
        self.assertEqual(len(database_corpus()['records']), 4)
        report = self.load(apply=True)
        removed.refresh_from_db()
        self.assertEqual(report['documents'], 3)
        self.assertEqual(report['searchable_documents'], 3)
        self.assertEqual(report['counts']['documents_retired'], 1)
        self.assertEqual(removed.review_status, 'withdrawn')
        self.assertEqual(removed.current_revision_id, revision_id)
        self.assertEqual(DocumentRevision.objects.get(pk=revision_id).body, original_body)
        self.assertEqual(removed.revisions.count(), 1)
        visible = database_corpus()
        self.assertEqual(len(visible['records']), report['searchable_documents'])
        self.assertNotIn(extra['metadata']['search_record']['id'], {row['id'] for row in visible['records']})
        self.assertEqual(KnowledgeDocument.objects.exclude(code__startswith='learning-').count(), 5)
        legacy.refresh_from_db()
        self.assertEqual((legacy.title, legacy.review_status, legacy.current_revision_id), ('原目录背景', 'draft', None))
        reviews = DocumentReview.objects.count()
        repeated = self.load(apply=True)
        self.assertEqual(repeated['counts']['documents_retired'], 0)
        self.assertEqual(DocumentReview.objects.count(), reviews)

    def test_manual_edit_and_foreign_ownership_are_preserved(self):
        first_code = self.packages[0]['documents'][0]['code']
        foreign = KnowledgeDocument.objects.create(code=first_code, title='已有独立文档')
        with self.assertRaisesMessage(PackageError, '归属不一致'):
            self.load(apply=True)
        self.assertEqual(KnowledgeDocument.objects.get(pk=foreign.pk).title, '已有独立文档')
        foreign.delete()
        self.load(apply=True)
        document = KnowledgeDocument.objects.get(code=first_code)
        document.title = '管理员已修改标题'
        document.save()
        before = DocumentRevision.objects.count()
        with self.assertRaisesMessage(PackageError, '当前标题或版本已修改'):
            self.load(apply=True)
        self.assertEqual(DocumentRevision.objects.count(), before)
        self.assertEqual(KnowledgeDocument.objects.get(pk=document.pk).title, document.title)

    def test_command_defaults_to_preview_and_outputs_json(self):
        output = StringIO()
        call_command('load_competition_knowledge', actor_id=self.actor.pk, reason=self.reason,
                     directory=str(self.directory), stdout=output)
        report = json.loads(output.getvalue())
        self.assertEqual(report['mode'], 'preview-rolled-back')
        self.assertEqual(report['searchable_documents'], 3)
        self.assertFalse(KnowledgeDocument.objects.exists())
