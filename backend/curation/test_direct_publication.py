"""直接发布可公开正文，但不会伪造核验或泄露关联草稿。"""

from io import StringIO
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import TestCase

from competitions.models import CompetitionSource, CompetitionTaxonomy
from governance.models import AdminAction

from .models import DocumentReview, DocumentRevision, ImportedObject, KnowledgeDocument
from .package import PackageError
from .services import publish_document
from .test_api import LibraryAPIFixtures


class DirectDocumentPublicationTests(LibraryAPIFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.publisher = get_user_model().objects.create_user(
            email='library-publisher@tongji.edu.cn', password='tests-only-password', is_staff=True,
        )
        cls.publisher.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='curation',
            codename__in=('change_knowledgedocument', 'add_documentreview'),
        ))
        cls.publisher.user_permissions.add(Permission.objects.get(
            content_type__app_label='competitions', codename='change_competition',
        ))

    def test_only_active_staff_with_both_publication_permissions_can_publish(self):
        for user in (None, self.student, self.limited, self.staff):
            with self.subTest(user=user):
                with self.assertRaises(PermissionDenied):
                    publish_document(self.draft_document.code, actor=user)
        self.publisher.is_active = False
        with self.assertRaises(PermissionDenied):
            publish_document(self.draft_document.code, actor=self.publisher)
        self.publisher.is_active = True
        self.publisher.is_staff = False
        with self.assertRaises(PermissionDenied):
            publish_document(self.draft_document.code, actor=self.publisher)
        self.assertEqual(DocumentReview.objects.count(), 0)
        self.draft_document.refresh_from_db()
        self.assertEqual(self.draft_document.review_status, 'draft')

    def test_publish_preserves_revision_sources_dates_and_verification_metadata(self):
        revision = self.draft_document.current_revision
        original = DocumentRevision.objects.filter(pk=revision.pk).values().get()
        result = publish_document(
            self.draft_document.code, actor=self.publisher, reason='  项目直接发布  ',
        )
        self.assertEqual(result.review_status, 'published')
        self.assertEqual(result.current_revision_id, revision.pk)
        self.assertEqual(DocumentRevision.objects.filter(pk=revision.pk).values().get(), original)
        self.assertEqual(result.revisions.count(), 1)
        record = result.reviews.get()
        self.assertEqual((record.status, record.reason, record.actor_id, record.revision_id),
                         ('published', '项目直接发布', self.publisher.pk, revision.pk))
        self.assertNotEqual(record.status, 'approved')
        self.draft_competition.refresh_from_db()
        self.draft_resource.refresh_from_db()
        self.assertEqual(self.draft_competition.publication_status, 'draft')
        self.assertEqual(self.draft_resource.publication_status, 'draft')

    def test_repeat_publication_and_existing_approval_do_not_create_records(self):
        first = publish_document(self.draft_document.code, actor=self.publisher)
        published_at = first.updated_at
        record_id = first.reviews.get().pk
        second = publish_document(self.draft_document.code, actor=self.publisher)
        self.assertEqual(second.updated_at, published_at)
        self.assertEqual(list(second.reviews.values_list('pk', flat=True)), [record_id])
        original_updated_at = self.public_document.updated_at
        approved = publish_document(self.public_document.code, actor=self.publisher)
        self.assertEqual(approved.review_status, 'approved')
        self.assertEqual(approved.updated_at, original_updated_at)
        self.assertFalse(approved.reviews.exists())

    def test_empty_body_missing_revision_and_withdrawn_documents_are_rejected(self):
        empty = self.make_document('empty-direct', 'draft', self.catalog, body=' \n ')
        absent = KnowledgeDocument.objects.create(code='absent-direct', title='无版本')
        withdrawn = self.make_document('withdrawn-direct', 'withdrawn', self.catalog)
        for document in (empty, absent, withdrawn):
            before = document.review_status
            with self.subTest(code=document.code):
                with self.assertRaises(PackageError):
                    publish_document(document.code, actor=self.publisher)
                document.refresh_from_db()
                self.assertEqual(document.review_status, before)
                self.assertFalse(document.reviews.exists())

    def test_publication_reason_must_be_nonempty_and_within_storage_limit(self):
        for reason in ('', '   ', 'x' * 501, None):
            with self.subTest(reason=reason):
                with self.assertRaises(PackageError):
                    publish_document(self.draft_document.code, actor=self.publisher, reason=reason)
        self.assertEqual(DocumentReview.objects.count(), 0)

    def test_publication_exposes_body_and_preserves_catalog_resource_associations(self):
        document = self.make_document(
            'direct-public-manual', 'draft', self.catalog, self.public_resource, self.public_competition,
        )
        self.assertEqual(self.client.get('/api/v1/knowledge-documents/direct-public-manual/').status_code, 404)
        publish_document(document.code, actor=self.publisher)
        detail = self.client.get('/api/v1/knowledge-documents/direct-public-manual/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['review_status'], 'published')
        self.assertEqual(detail.data['body'], document.current_revision.body)
        self.assertEqual(detail.data['version'], document.current_revision.version)
        listing = self.client.get('/api/v1/knowledge-documents/', {'catalog_code': self.catalog.code})
        self.assertEqual(listing.data['count'], 2)
        catalog = self.client.get('/api/v1/competition-catalog/' + self.catalog.code + '/').data
        self.assertEqual((catalog['competition_count'], catalog['resource_count'], catalog['document_count']),
                         (1, 1, 2))
        resources = self.client.get('/api/v1/resources/', {'catalog_code': self.catalog.code}).data
        self.assertEqual(resources['count'], 1)
        self.assertEqual(resources['results'][0]['catalogs'],
                         [{'code': self.catalog.code, 'name': self.catalog.name}])

    def test_direct_publication_does_not_bypass_hidden_target_visibility(self):
        cases = (
            self.make_document('direct-draft-resource', 'draft', self.catalog, self.draft_resource),
            self.make_document('direct-draft-edition', 'draft', self.catalog, competition=self.draft_competition),
            self.make_document('direct-withdrawn-edition', 'draft', self.catalog,
                               competition=self.withdrawn_competition),
        )
        for document in cases:
            with self.subTest(code=document.code):
                publish_document(document.code, actor=self.publisher)
                self.assertEqual(self.client.get('/api/v1/knowledge-documents/' + document.code + '/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/knowledge-documents/').data['count'], 1)
        catalog = self.client.get('/api/v1/competition-catalog/' + self.catalog.code + '/').data
        self.assertEqual((catalog['competition_count'], catalog['resource_count'], catalog['document_count']),
                         (1, 1, 1))

    def make_package(self, package_id, *, document=None, competition=None):
        for kind, value in (('document', document), ('competition', competition)):
            if value is not None:
                ImportedObject.objects.create(
                    kind=kind, code=value.code, package_id=package_id,
                    payload_hash='1' * 64, state_hash='2' * 64,
                )

    def test_package_command_defaults_to_preview_without_any_write(self):
        self.make_package('selected-package', document=self.draft_document, competition=self.draft_competition)
        previous_document = KnowledgeDocument.objects.filter(pk=self.draft_document.pk).values().get()
        previous_competition = type(self.draft_competition).objects.filter(pk=self.draft_competition.pk).values().get()
        previous_counts = (DocumentReview.objects.count(), AdminAction.objects.count(), CompetitionTaxonomy.objects.count())
        output = StringIO()
        call_command('publish_curated_library', '--package-id', 'selected-package', stdout=output)
        self.assertEqual(json.loads(output.getvalue()), {'mode': 'preview', 'competitions': 1, 'documents': 1})
        self.assertEqual(KnowledgeDocument.objects.filter(pk=self.draft_document.pk).values().get(), previous_document)
        self.assertEqual(type(self.draft_competition).objects.filter(pk=self.draft_competition.pk).values().get(), previous_competition)
        self.assertEqual((DocumentReview.objects.count(), AdminAction.objects.count(), CompetitionTaxonomy.objects.count()),
                         previous_counts)

    def test_package_command_limits_scope_and_repeated_run_adds_no_publication_record(self):
        source = CompetitionSource.objects.create(
            competition=self.draft_competition, source_type='official', source_name='赛事官网',
            source_url='https://www.robomaster.com/zh-CN/robo/training-system', is_primary=True,
        )
        outside = self.make_document('outside-selected-package', 'draft', self.second_catalog)
        self.make_package('selected-package', document=self.draft_document, competition=self.draft_competition)
        self.make_package('other-package', document=outside)
        original_revision = self.draft_document.current_revision_id
        arguments = ('publish_curated_library', '--package-id', 'selected-package')
        first_output = StringIO()
        call_command(*arguments, actor_id=self.publisher.pk, apply=True, stdout=first_output)
        first = json.loads(first_output.getvalue())
        self.assertEqual((first['documents_published'], first['competitions_published']), (1, 1))
        outside.refresh_from_db()
        self.assertEqual(outside.review_status, 'draft')
        self.assertFalse(outside.reviews.exists())
        self.draft_document.refresh_from_db()
        self.assertEqual(self.draft_document.current_revision_id, original_revision)
        self.assertEqual(self.draft_document.review_status, 'published')
        source.refresh_from_db()
        self.assertIsNone(source.last_verified_at)
        before_records = (list(DocumentReview.objects.values_list('pk', flat=True)),
                          list(AdminAction.objects.values_list('pk', flat=True)))
        published_at = self.draft_document.updated_at
        second_output = StringIO()
        call_command(*arguments, actor_id=self.publisher.pk, apply=True, stdout=second_output)
        second = json.loads(second_output.getvalue())
        self.assertEqual((second['documents_unchanged'], second['competitions_unchanged']), (1, 1))
        self.assertEqual((list(DocumentReview.objects.values_list('pk', flat=True)),
                          list(AdminAction.objects.values_list('pk', flat=True))), before_records)
        self.draft_document.refresh_from_db()
        self.assertEqual(self.draft_document.updated_at, published_at)
