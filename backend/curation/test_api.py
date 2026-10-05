"""Integration tests for the manual library HTTP boundary and profile capability."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from competition_catalog.models import CatalogBinding, CatalogEntry
from competitions.models import Competition, CompetitionTaxonomy
from resources.models import Resource, ResourceTaxonomy

from .api_permissions import LIBRARY_VIEW_PERMISSIONS, can_preview_library
from .models import DocumentLink, DocumentRevision, KnowledgeDocument


class LibraryAPIFixtures:
    """Shared domain examples, independent of any local import or real database."""

    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.student = users.create_user(email='library-student@tongji.edu.cn', password='tests-only-password')
        cls.staff = users.create_user(email='library-staff@tongji.edu.cn', password='tests-only-password', is_staff=True)
        cls.limited = users.create_user(email='library-limited@tongji.edu.cn', password='tests-only-password', is_staff=True)
        for permission in LIBRARY_VIEW_PERMISSIONS:
            app, code = permission.split('.')
            cls.staff.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=code))
        cls.limited.user_permissions.add(Permission.objects.get(content_type__app_label='curation', codename='view_knowledgedocument'))
        cls.category = CompetitionTaxonomy.objects.create(code='engineering', kind='category', name='工程')
        cls.resource_category = ResourceTaxonomy.objects.create(code='course', kind='category', name='学习课程')
        cls.catalog = cls.make_catalog('2026001', name='工程设计赛事')
        cls.second_catalog = cls.make_catalog('2026002', name='数学建模赛事', grade='B')
        cls.inactive_catalog = cls.make_catalog('2026003', name='已停用目录', is_active=False)
        cls.public_competition = cls.make_competition('engineering-2026')
        cls.draft_competition = cls.make_competition('engineering-draft', status='draft')
        cls.withdrawn_competition = cls.make_competition('engineering-withdrawn', status='withdrawn')
        for competition in (cls.public_competition, cls.draft_competition, cls.withdrawn_competition):
            CatalogBinding.objects.create(entry=cls.catalog, competition=competition, basis='资料匹配')
        cls.public_resource = cls.make_resource('public-course')
        cls.draft_resource = cls.make_resource('draft-course', status='draft')
        cls.public_document = cls.make_document('public-manual', 'approved', cls.catalog,
                                                cls.public_resource, cls.public_competition)
        cls.draft_document = cls.make_document('draft-manual', 'draft', cls.catalog,
                                               cls.draft_resource, cls.draft_competition)

    @classmethod
    def make_catalog(cls, code, **overrides):
        data = dict(code=code, name='目录 ' + code, grade='A', levels='国家级',
                    departments=['测试学院'], source_url='https://www.tongji.edu.cn/competitions')
        data.update(overrides)
        return CatalogEntry.objects.create(**data)

    @classmethod
    def make_competition(cls, code, status='published'):
        return Competition.objects.create(code=code, title='赛事 ' + code, edition='2026 年度',
            summary='当前届次摘要', description='已整理的规则', category=cls.category,
            publication_status=status, last_verified_at=timezone.now(),
            published_at=None if status == 'draft' else timezone.now(),
            withdrawal_reason='内容撤下' if status == 'withdrawn' else '')

    @classmethod
    def make_resource(cls, code, status='published'):
        return Resource.objects.create(code=code, title='学习资料 ' + code, description='公开课程介绍',
            category=cls.resource_category, access_url='https://www.robomaster.com/zh-CN/robo/training-system',
            publication_status=status, published_at=None if status == 'draft' else timezone.now(),
            withdrawal_reason='资料撤下' if status == 'withdrawn' else '')

    @classmethod
    def make_document(cls, code, status='approved', catalog=None, resource=None, competition=None, **revision_fields):
        document = KnowledgeDocument.objects.create(code=code, title='旧主表标题', review_status='draft')
        revision = cls.make_revision(document, 1, catalog, resource, competition, **revision_fields)
        document.current_revision = revision
        document.review_status = status
        document.save()
        return document

    @classmethod
    def make_revision(cls, document, version, catalog=None, resource=None, competition=None, **overrides):
        data = dict(document=document, version=version, title='当前版本手册 ' + document.code,
            body='工程规则说明\n人工整理的学习资料', edition='2026', content_hash=str(version) * 64,
            created_by=cls.staff, sources=[{'url': 'https://www.tongji.edu.cn/rules', 'title': '官方规则'}],
            attachments=[{'path': 'C:/private/manual.pdf', 'sha256': '0' * 64}],
            metadata={'private_path': 'C:/private/manual.pdf', 'operator_email': 'hidden@tongji.edu.cn',
                      'edition_note': '版本说明', 'gaps': ['缺少赛题附件'], 'contains_source_fulltext': False})
        data.update(overrides)
        revision = DocumentRevision.objects.create(**data)
        for field, value in (('catalog', catalog), ('resource', resource), ('competition', competition)):
            if value is not None:
                DocumentLink.objects.create(revision=revision, **{field: value})
        return revision

    def setUp(self):
        self.client = APIClient()


class KnowledgeDocumentAPITests(LibraryAPIFixtures, TestCase):
    def test_public_list_and_detail_are_current_approved_and_whitelisted(self):
        response = self.client.get('/api/v1/knowledge-documents/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        row = response.data['results'][0]
        self.assertEqual(row['code'], 'public-manual')
        self.assertEqual(row['title'], '当前版本手册 public-manual')
        self.assertNotIn('body', row)
        detail = self.client.get('/api/v1/knowledge-documents/public-manual/')
        self.assertEqual(detail.data['body'], '工程规则说明\n人工整理的学习资料')
        self.assertEqual(detail.data['notes']['edition_note'], '版本说明')
        self.assertEqual(detail.data['notes']['gaps'], ['缺少赛题附件'])
        self.assertFalse(detail.data['notes']['contains_source_fulltext'])
        self.assertNotIn('C:/private', str(detail.data))
        self.assertNotIn('operator_email', str(detail.data))
        self.assertNotIn('hidden@', str(detail.data))
        self.assertNotIn('attachments', detail.data)
        self.assertEqual(detail['Cache-Control'], 'private, no-store')

    def test_preview_is_denied_to_anonymous_students_and_partial_staff(self):
        for user in (None, self.student, self.limited):
            self.client.force_authenticate(user=user)
            for endpoint in ('', 'draft-manual/'):
                with self.subTest(user=user, endpoint=endpoint):
                    self.assertEqual(self.client.get('/api/v1/knowledge-documents/' + endpoint,
                                                     {'preview': '1'}).status_code, 403)
        self.client.force_authenticate(user=self.staff)
        self.assertEqual(self.client.get('/api/v1/knowledge-documents/', {'preview': '1'}).data['count'], 2)
        self.assertEqual(self.client.get('/api/v1/knowledge-documents/draft-manual/', {'preview': 'true'}).status_code, 200)
        self.staff.is_active = False
        self.assertEqual(self.client.get('/api/v1/knowledge-documents/', {'preview': '1'}).status_code, 403)

    def test_draft_withdrawn_empty_and_hidden_linked_documents_are_excluded(self):
        self.make_document('withdrawn-manual', 'withdrawn', self.catalog)
        KnowledgeDocument.objects.create(code='empty-manual', title='尚无正文', review_status='draft')
        self.make_document('approved-draft-link', 'approved', self.catalog, self.draft_resource)
        self.make_document('approved-withdrawn-link', 'approved', self.catalog, competition=self.withdrawn_competition)
        unavailable = self.make_resource('unavailable-course')
        unavailable.availability = 'unavailable'
        unavailable.save()
        self.make_document('approved-unavailable-link', 'approved', self.catalog, unavailable)
        self.assertEqual(self.client.get('/api/v1/knowledge-documents/').data['count'], 1)
        for code in ('draft-manual', 'withdrawn-manual', 'empty-manual', 'approved-draft-link',
                     'approved-withdrawn-link', 'approved-unavailable-link'):
            self.assertEqual(self.client.get('/api/v1/knowledge-documents/' + code + '/').status_code, 404)

    def test_public_reader_ignores_old_body_and_links_after_revision_change(self):
        revision = self.make_revision(self.public_document, 2, self.second_catalog, self.public_resource,
                                      body='新版本独有内容', title='更新手册')
        self.public_document.current_revision = revision
        self.public_document.save()
        self.assertEqual(self.client.get('/api/v1/knowledge-documents/public-manual/').data['version'], 2)
        self.assertEqual(self.client.get('/api/v1/knowledge-documents/', {'catalog_code': self.catalog.code}).data['count'], 0)
        self.assertEqual(self.client.get('/api/v1/knowledge-documents/', {'catalog_code': self.second_catalog.code}).data['count'], 1)
        self.assertEqual(self.client.get('/api/v1/knowledge-documents/', {'search': '新版本独有'}).data['count'], 1)
        self.assertEqual(self.client.get('/api/v1/knowledge-documents/', {'search': '工程规则'}).data['count'], 0)

    def test_inactive_catalog_is_not_a_public_filter_relation(self):
        DocumentLink.objects.create(revision=self.public_document.current_revision, catalog=self.inactive_catalog)
        self.assertEqual(self.client.get('/api/v1/knowledge-documents/', {'catalog_code': self.inactive_catalog.code}).data['count'], 0)

    def test_source_whitelist_deduplicates_and_removes_private_or_credential_urls(self):
        revision = self.make_revision(self.public_document, 2, self.catalog, self.public_resource,
            body='<b>正文</b>\n邮箱：private@tongji.edu.cn\n电话：13800138000\n学习说明',
            sources=[{'url': 'https://www.tongji.edu.cn/rules#top', 'locator': '规则原文', 'path': 'C:/private'},
                     {'url': 'https://www.tongji.edu.cn/rules', 'title': '重复'},
                     {'url': 'http://127.0.0.1/private'}, {'url': 'file:///C:/private/a.pdf'},
                     {'url': 'https://www.tongji.edu.cn/rules?token=secret'},
                     {'url': 'https://name:password@www.tongji.edu.cn/rules'}, 'bad-source'])
        self.public_document.current_revision = revision
        self.public_document.save()
        result = self.client.get('/api/v1/knowledge-documents/public-manual/').data
        self.assertEqual(result['sources'], [{'url': 'https://www.tongji.edu.cn/rules', 'title': '规则原文'}])
        self.assertEqual(result['body'], '正文\n学习说明')

    def test_filter_bounds_bad_preview_and_pagination(self):
        for params in ({'search': 'x' * 201}, {'catalog_code': 'x' * 17}, {'preview': 'yes'},
                       {'page_size': 0}, {'page_size': 'abc'}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get('/api/v1/knowledge-documents/', params).status_code, 400)
        for number in range(51):
            self.make_document(f'guide-{number:02}', 'approved', self.catalog)
        result = self.client.get('/api/v1/knowledge-documents/', {'page_size': 200})
        self.assertEqual(result.data['count'], 52)
        self.assertEqual(len(result.data['results']), 50)
        self.assertEqual(len(self.client.get('/api/v1/knowledge-documents/').data['results']), 20)
        second = self.client.get('/api/v1/knowledge-documents/', {'page_size': 200, 'page': 2})
        self.assertEqual(len(second.data['results']), 2)
        self.assertFalse({r['code'] for r in result.data['results']} & {r['code'] for r in second.data['results']})

    def test_reading_all_library_endpoints_does_not_open_network_connections(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('No network during library reads')), \
             patch('socket.create_connection', side_effect=AssertionError('No network during library reads')):
            for endpoint in ('/api/v1/knowledge-documents/', '/api/v1/knowledge-documents/public-manual/',
                             '/api/v1/competition-catalog/', '/api/v1/competition-catalog/2026001/'):
                self.assertEqual(self.client.get(endpoint).status_code, 200)

    def test_me_reports_capability_without_granting_ordinary_login_preview(self):
        self.assertEqual(self.client.get('/api/v1/accounts/me/').status_code, 403)
        for user, expected in ((self.student, False), (self.limited, False), (self.staff, True)):
            self.client.force_authenticate(user=user)
            result = self.client.get('/api/v1/accounts/me/')
            self.assertEqual(result.status_code, 200)
            self.assertIs(result.data['can_preview_library'], expected)
            self.assertEqual(result['Cache-Control'], 'no-store')
        self.staff.is_staff = False
        self.assertFalse(can_preview_library(self.staff))
        self.staff.is_staff = True
        self.staff.is_active = False
        self.assertFalse(can_preview_library(self.staff))
