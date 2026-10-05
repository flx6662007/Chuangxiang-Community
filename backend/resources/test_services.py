"""Publishing is authorized, atomic and independent of linked competition/document review."""

from datetime import timedelta
import io
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from competitions.models import Competition
from curation.models import DocumentLink, DocumentRevision, ImportedObject, KnowledgeDocument

from .models import Resource, ResourceCompetition, ResourceDirection, ResourceRevision, ResourceTag, ResourceTaxonomy
from .services import publish_resource


class PublishResourceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.actor = users.create_user(email='publisher@tongji.edu.cn', password='tests-only-password', is_staff=True)
        cls.no_permission = users.create_user(email='reader@tongji.edu.cn', password='tests-only-password', is_staff=True)
        cls.student = users.create_user(email='reader-student@tongji.edu.cn', password='tests-only-password')
        change = Permission.objects.get(content_type__app_label='resources', codename='change_resource')
        cls.actor.user_permissions.add(change)
        cls.student.user_permissions.add(change)
        cls.category = ResourceTaxonomy.objects.create(code='manual', kind='category', name='参赛手册')
        cls.other_category = ResourceTaxonomy.objects.create(code='course', kind='category', name='学习课程')
        cls.inactive_category = ResourceTaxonomy.objects.create(code='old', kind='category', name='停用类别', is_active=False)
        cls.tag = ResourceTaxonomy.objects.create(code='beginner', kind='tag', name='入门')
        cls.direction = ResourceTaxonomy.objects.create(code='robots', kind='direction', name='机器人')
        cls.resource = Resource.objects.create(code='manual-to-publish', title='学习手册', description='公开学习资料说明',
            access_url='https://www.robomaster.com/zh-CN/robo/training-system', source_note='来源索引已整理',
            created_by=cls.actor)

    def assert_draft_unchanged(self):
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.publication_status, 'draft')
        self.assertIsNone(self.resource.published_at)
        self.assertEqual(self.resource.content_version, 1)
        self.assertFalse(ResourceRevision.objects.filter(resource=self.resource).exists())

    def test_requires_active_staff_and_change_permission_before_any_write(self):
        for actor in (None, AnonymousUser(), self.no_permission, self.student):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                publish_resource(self.resource.pk, actor=actor, category=self.category)
            self.assert_draft_unchanged()
        self.actor.is_active = False
        with self.assertRaises(PermissionDenied):
            publish_resource(self.resource.pk, actor=self.actor, category=self.category)
        self.assert_draft_unchanged()

    def test_valid_publication_assigns_category_and_creates_content_snapshot(self):
        ResourceTag.objects.create(resource=self.resource, taxonomy=self.tag)
        ResourceDirection.objects.create(resource=self.resource, taxonomy=self.direction)
        published = publish_resource(self.resource.pk, actor=self.actor, category=self.category)
        self.assertEqual(published.publication_status, 'published')
        self.assertEqual(published.category_id, self.category.pk)
        self.assertEqual(published.content_version, 2)
        self.assertEqual(published.updated_by_id, self.actor.pk)
        self.assertIsNotNone(published.published_at)
        self.assertEqual(published.last_edited_at, published.published_at)
        self.assertIsNone(published.last_verified_at)
        revision = ResourceRevision.objects.get(resource=published)
        self.assertEqual(revision.version, 2)
        self.assertEqual(revision.created_by_id, self.actor.pk)
        self.assertEqual(revision.snapshot['content_version'], 2)
        self.assertEqual(revision.snapshot['title'], '学习手册')
        self.assertEqual(revision.snapshot['category'], 'manual')
        self.assertEqual(revision.snapshot['tags'], ['beginner'])
        self.assertEqual(revision.snapshot['directions'], ['robots'])
        self.assertEqual(revision.snapshot['competitions'], [])
        self.assertNotIn('created_by', revision.snapshot)
        self.assertNotIn('password', revision.snapshot)

    def test_missing_wrong_kind_and_new_inactive_category_block_publication(self):
        for category in (None, self.tag, self.direction, self.inactive_category):
            with self.subTest(category=category), self.assertRaises(ValidationError):
                publish_resource(self.resource.pk, actor=self.actor, category=category)
            self.assert_draft_unchanged()
            self.assertIsNone(self.resource.category_id)

    def test_unsafe_or_absent_public_source_is_rejected_atomically(self):
        urls = ('', 'file:///C:/private/guide.pdf', 'http://127.0.0.1/private', 'http://service.internal/docs',
                'https://www.robomaster.com/guide?token=secret', 'https://name:password@www.robomaster.com/guide')
        for url in urls:
            self.resource.access_url = url
            self.resource.save(update_fields=['access_url'])
            with self.subTest(url=url), self.assertRaises(ValidationError):
                publish_resource(self.resource.pk, actor=self.actor, category=self.category)
            self.assert_draft_unchanged()

    def test_missing_or_contact_only_public_text_is_rejected(self):
        for field, value in (('title', ''), ('description', ''), ('title', '<br>'),
                             ('description', '邮箱：private@tongji.edu.cn\n电话：13800138000')):
            self.resource.title = '学习手册'
            self.resource.description = '正常介绍'
            setattr(self.resource, field, value)
            self.resource.save()
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                publish_resource(self.resource.pk, actor=self.actor, category=self.category)
            self.assert_draft_unchanged()

    def test_unavailable_draft_and_withdrawn_resource_cannot_be_published(self):
        self.resource.availability = 'unavailable'
        self.resource.save()
        with self.assertRaises(ValidationError):
            publish_resource(self.resource.pk, actor=self.actor, category=self.category)
        self.assert_draft_unchanged()
        self.resource.availability = 'available'
        self.resource.publication_status = 'withdrawn'
        self.resource.published_at = timezone.now() - timedelta(days=1)
        self.resource.withdrawal_reason = '失效资料'
        self.resource.save()
        with self.assertRaises(ValidationError):
            publish_resource(self.resource.pk, actor=self.actor, category=self.category)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.publication_status, 'withdrawn')
        self.assertEqual(self.resource.withdrawal_reason, '失效资料')
        self.assertFalse(ResourceRevision.objects.filter(resource=self.resource).exists())

    def test_repeat_publication_preserves_version_snapshot_times_and_category(self):
        ResourceRevision.objects.create(resource=self.resource, version=1,
            snapshot={'title': '首次整理', 'content_version': 1}, created_by=self.actor)
        old_verified_at = timezone.now() - timedelta(days=10)
        self.resource.last_verified_at = old_verified_at
        self.resource.save()
        first = publish_resource(self.resource.pk, actor=self.actor, category=self.category)
        first_updated_at = first.updated_at
        second = publish_resource(self.resource.pk, actor=self.actor, category=self.other_category)
        self.assertEqual(second.content_version, 2)
        self.assertEqual(second.published_at, first.published_at)
        self.assertEqual(second.updated_at, first_updated_at)
        self.assertEqual(second.category_id, self.category.pk)
        self.assertEqual(second.last_verified_at, old_verified_at)
        self.assertEqual(list(ResourceRevision.objects.filter(resource=self.resource).order_by('version')
                              .values_list('version', flat=True)), [1, 2])
        self.assertEqual(ResourceRevision.objects.get(resource=self.resource, version=1).snapshot,
                         {'title': '首次整理', 'content_version': 1})

    def test_snapshot_failure_rolls_back_publication_not_just_revision(self):
        with patch.object(ResourceRevision, 'save', side_effect=ValidationError('模拟快照写入失败')):
            with self.assertRaises(ValidationError):
                publish_resource(self.resource.pk, actor=self.actor, category=self.category)
        self.assert_draft_unchanged()
        self.assertIsNone(self.resource.category_id)
        self.assertIsNone(self.resource.last_edited_at)

    def test_publishing_resource_does_not_publish_or_revise_related_knowledge_and_competition(self):
        competition = Competition.objects.create(code='draft-related-competition', title='未发布赛事', edition='2026')
        ResourceCompetition.objects.create(resource=self.resource, competition=competition)
        document = KnowledgeDocument.objects.create(code='draft-related-document', title='内部正文', review_status='draft')
        document_revision = DocumentRevision.objects.create(document=document, version=1, title='内部正文',
            body='仍待审核的原始资料', content_hash='1' * 64, created_by=self.actor)
        DocumentLink.objects.create(revision=document_revision, resource=self.resource)
        DocumentLink.objects.create(revision=document_revision, competition=competition)
        document.current_revision = document_revision
        document.save()
        old_document_time = document.updated_at
        old_competition_time = competition.updated_at
        publish_resource(self.resource.pk, actor=self.actor, category=self.category)
        document.refresh_from_db()
        competition.refresh_from_db()
        self.assertEqual(document.review_status, 'draft')
        self.assertEqual(document.current_revision_id, document_revision.pk)
        self.assertEqual(document.updated_at, old_document_time)
        self.assertEqual(document.revisions.count(), 1)
        self.assertEqual(competition.publication_status, 'draft')
        self.assertIsNone(competition.published_at)
        self.assertEqual(competition.updated_at, old_competition_time)
        self.assertEqual(ResourceRevision.objects.get(resource=self.resource).snapshot['competitions'],
                         ['draft-related-competition'])

    def test_command_without_apply_reports_scope_without_writes(self):
        ImportedObject.objects.create(kind='resource', code=self.resource.code, package_id='test-learning-package',
                                      payload_hash='0' * 64, state_hash='1' * 64)
        initial_categories = ResourceTaxonomy.objects.count()
        output = io.StringIO()
        call_command('publish_curated_resources', '--package-id', 'test-learning-package', stdout=output)
        self.assertEqual(json.loads(output.getvalue()), {'total': 1, 'draft': 1, 'published': 0, 'mode': 'preview'})
        self.assertEqual(ResourceTaxonomy.objects.count(), initial_categories)
        self.assert_draft_unchanged()

    def test_apply_command_is_idempotent_and_only_publishes_selected_package(self):
        ImportedObject.objects.create(kind='resource', code=self.resource.code, package_id='test-learning-package',
                                      payload_hash='0' * 64, state_hash='1' * 64)
        outside = Resource.objects.create(code='outside-package', title='其他包资料', description='学习说明')
        ImportedObject.objects.create(kind='resource', code=outside.code, package_id='another-package',
                                      payload_hash='0' * 64, state_hash='1' * 64)
        for _ in range(2):
            output = io.StringIO()
            call_command('publish_curated_resources', '--package-id', 'test-learning-package',
                         '--actor-id', str(self.actor.pk), '--apply', stdout=output)
            self.assertEqual(json.loads(output.getvalue())['published_after'], 1)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.publication_status, 'published')
        self.assertEqual(self.resource.category.code, 'competition-learning')
        self.assertEqual(self.resource.category.name, '赛事学习资料')
        self.assertEqual(self.resource.content_version, 2)
        self.assertEqual(ResourceRevision.objects.filter(resource=self.resource).count(), 1)
        outside.refresh_from_db()
        self.assertEqual(outside.publication_status, 'draft')
        self.assertEqual(outside.content_version, 1)
