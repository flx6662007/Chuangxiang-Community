"""Public resource boundaries tested with an isolated SQLite database and no network."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import include, path
from django.utils import timezone
from rest_framework.test import APIClient

from competition_catalog.models import CatalogEntry
from competitions.models import Competition
from curation.models import DocumentLink, DocumentRevision, KnowledgeDocument

from .models import Resource, ResourceDirection, ResourceTaxonomy
from .selectors import visible_resources


urlpatterns = [path('api/v1/resources/', include('resources.urls'))]


@override_settings(ROOT_URLCONF=__name__)
class ResourceAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.student = users.create_user(email='resource-student@tongji.edu.cn', password='tests-only-password')
        cls.staff = users.create_user(email='resource-staff@tongji.edu.cn', password='tests-only-password', is_staff=True)
        cls.limited = users.create_user(email='resource-limited@tongji.edu.cn', password='tests-only-password', is_staff=True)
        permissions = [('competition_catalog', 'view_catalogentry'), ('competitions', 'view_competition'),
                       ('resources', 'view_resource'), ('curation', 'view_knowledgedocument')]
        cls.staff.user_permissions.add(*[Permission.objects.get(content_type__app_label=app, codename=code)
                                        for app, code in permissions])
        cls.limited.user_permissions.add(Permission.objects.get(content_type__app_label='resources', codename='view_resource'))
        cls.category = ResourceTaxonomy.objects.create(code='rules', kind='category', name='竞赛规则')
        cls.direction = ResourceTaxonomy.objects.create(code='robotics', kind='direction', name='机器人')
        cls.unused = ResourceTaxonomy.objects.create(code='unused', kind='category', name='未使用类别')
        cls.resource = cls.make_resource('official-rule', description='规则正文' + '学习说明' * 100)
        ResourceDirection.objects.create(resource=cls.resource, taxonomy=cls.direction)
        cls.draft = cls.make_resource('draft-rule', publication_status='draft', category=None)
        cls.withdrawn = cls.make_resource('withdrawn-rule', publication_status='withdrawn')
        cls.unavailable = cls.make_resource('unavailable-rule', availability='unavailable')
        cls.catalog = CatalogEntry.objects.create(code='2026001', name='公开目录', grade='A', levels='国家级',
                                                   source_url='https://www.tongji.edu.cn/catalog')
        cls.other_catalog = CatalogEntry.objects.create(code='2026002', name='另一个目录', grade='A', levels='国家级',
                                                         source_url='https://www.tongji.edu.cn/catalog')
        cls.document = KnowledgeDocument.objects.create(code='rule-document', title='规则正文', review_status='draft')
        cls.revision = cls.make_revision(cls.document, 1, cls.catalog, cls.resource)
        cls.document.current_revision = cls.revision
        cls.document.review_status = 'approved'
        cls.document.save()

    @classmethod
    def make_resource(cls, code, **overrides):
        values = dict(code=code, title='学习资源 ' + code, description='公开规则说明', category=cls.category,
                      access_url='https://www.robomaster.com/zh-CN/robo/training-system', provider='官方组织',
                      publication_status='published', published_at=timezone.now())
        values.update(overrides)
        if values['publication_status'] == 'draft':
            values['published_at'] = None
        if values['publication_status'] == 'withdrawn':
            values['withdrawal_reason'] = '测试撤下'
        return Resource.objects.create(**values)

    @classmethod
    def make_revision(cls, document, version, catalog, resource):
        revision = DocumentRevision.objects.create(document=document, version=version, title='规则正文',
            body='资料正文', content_hash=str(version) * 64, created_by=cls.staff,
            metadata={'private_path': 'C:/private/source.docx', 'email': 'hidden@tongji.edu.cn'},
            attachments=[{'path': 'C:/private/source.docx'}])
        DocumentLink.objects.create(revision=revision, resource=resource)
        DocumentLink.objects.create(revision=revision, catalog=catalog)
        return revision

    def setUp(self):
        self.client = APIClient()

    def test_public_list_and_detail_use_stable_code_and_explicit_fields(self):
        response = self.client.get('/api/v1/resources/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        row = response.data['results'][0]
        self.assertEqual(row['id'], 'official-rule')
        self.assertEqual(len(row['description']), 280)
        self.assertEqual(row['content'], '')
        self.assertEqual(row['catalogs'], [{'code': '2026001', 'name': '公开目录'}])
        detail = self.client.get('/api/v1/resources/official-rule/').data
        self.assertEqual(detail['content'], self.resource.description)
        self.assertEqual(set(detail), {'id', 'title', 'description', 'content', 'category', 'directions',
            'tags', 'provider', 'source_url', 'updated_at', 'publication_status', 'availability', 'catalogs', 'facts'})
        self.assertNotIn('private', str(detail))
        self.assertNotIn('hidden@', str(detail))
        self.assertEqual(self.client.get(f'/api/v1/resources/{self.resource.pk}/').status_code, 404)

    def test_preview_requires_active_staff_with_all_library_permissions(self):
        for user in (None, self.student, self.limited):
            self.client.force_authenticate(user=user)
            for endpoint in ('', 'options/', 'draft-rule/'):
                with self.subTest(user=user, endpoint=endpoint):
                    self.assertEqual(self.client.get('/api/v1/resources/' + endpoint, {'preview': '1'}).status_code, 403)
        self.client.force_authenticate(user=self.staff)
        self.assertEqual(self.client.get('/api/v1/resources/', {'preview': 'true'}).data['count'], 2)
        self.assertEqual(self.client.get('/api/v1/resources/draft-rule/', {'preview': '1'}).status_code, 200)
        self.staff.is_active = False
        self.assertEqual(self.client.get('/api/v1/resources/', {'preview': '1'}).status_code, 403)

    def test_explicit_false_is_public_and_bad_preview_is_rejected(self):
        for value in ('0', 'false'):
            self.assertEqual(self.client.get('/api/v1/resources/', {'preview': value}).data['count'], 1)
        self.assertEqual(self.client.get('/api/v1/resources/', {'preview': 'yes'}).status_code, 400)

    def test_draft_withdrawn_unavailable_and_demo_are_hidden(self):
        self.make_resource('demo-training')
        self.make_resource('fictional', title='【虚构样例】学习')
        self.assertEqual(list(visible_resources().values_list('code', flat=True)), ['official-rule'])
        for code in ('draft-rule', 'withdrawn-rule', 'unavailable-rule', 'demo-training', 'fictional'):
            self.assertEqual(self.client.get('/api/v1/resources/' + code + '/').status_code, 404)
        self.client.force_authenticate(user=self.staff)
        for code in ('withdrawn-rule', 'unavailable-rule'):
            self.assertEqual(self.client.get('/api/v1/resources/' + code + '/', {'preview': '1'}).status_code, 404)

    def test_current_resource_links_do_not_require_document_approval(self):
        revision2 = self.make_revision(self.document, 2, self.other_catalog, self.resource)
        self.document.current_revision = revision2
        self.document.save()
        self.assertEqual(self.client.get('/api/v1/resources/official-rule/').data['catalogs'],
                         [{'code': '2026002', 'name': '另一个目录'}])
        self.assertEqual(self.client.get('/api/v1/resources/', {'catalog_code': '2026001'}).data['count'], 0)
        self.assertEqual(self.client.get('/api/v1/resources/', {'catalog_code': '2026002'}).data['count'], 1)
        self.document.review_status = 'draft'
        self.document.save()
        self.assertEqual(self.client.get('/api/v1/resources/official-rule/').data['catalogs'],
                         [{'code': '2026002', 'name': '另一个目录'}])
        self.assertEqual(self.client.get('/api/v1/resources/', {'catalog_code': '2026002'}).data['count'], 1)
        self.client.force_authenticate(user=self.staff)
        self.assertEqual(len(self.client.get('/api/v1/resources/official-rule/', {'preview': '1'}).data['catalogs']), 1)
        self.document.review_status = 'withdrawn'
        self.document.save()
        self.assertEqual(self.client.get('/api/v1/resources/official-rule/', {'preview': '1'}).data['catalogs'], [])
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get('/api/v1/resources/official-rule/').data['catalogs'], [])
        self.assertEqual(self.client.get('/api/v1/resources/', {'catalog_code': '2026002'}).data['count'], 0)

    def test_public_resource_association_survives_hidden_sibling_without_revealing_it(self):
        DocumentLink.objects.create(revision=self.revision, resource=self.draft)
        self.document.review_status = 'draft'
        self.document.save()
        self.assertEqual(self.client.get('/api/v1/resources/official-rule/').data['catalogs'],
                         [{'code': '2026001', 'name': '公开目录'}])
        result = self.client.get('/api/v1/resources/', {'catalog_code': '2026001'}).data
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['results'][0]['id'], 'official-rule')
        self.assertEqual(self.client.get('/api/v1/resources/draft-rule/').status_code, 404)

    def test_public_resource_association_does_not_require_published_competition(self):
        draft_competition = Competition.objects.create(code='draft-competition', title='未发布届次', edition='2026')
        DocumentLink.objects.create(revision=self.revision, competition=draft_competition)
        self.document.review_status = 'draft'
        self.document.save()
        response = self.client.get('/api/v1/resources/', {'catalog_code': '2026001'})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['catalogs'], [{'code': '2026001', 'name': '公开目录'}])
        self.assertNotIn('未发布届次', str(response.data))
        self.assertNotIn('资料正文', str(response.data))
        self.assertNotIn('private', str(response.data))

    def test_inactive_catalog_is_not_exposed_in_resource_associations(self):
        self.catalog.is_active = False
        self.catalog.save()
        self.assertEqual(self.client.get('/api/v1/resources/official-rule/').data['catalogs'], [])

    def test_source_urls_are_public_and_text_is_sanitized(self):
        self.resource.access_url = 'https://127.0.0.1/private?token=hidden'
        self.resource.description = '<b>公开资料</b>\n联系人：张同学\n邮箱：private@tongji.edu.cn\n可阅读'
        self.resource.provider = '单位：校内\n电话：13800138000'
        self.resource.save()
        result = self.client.get('/api/v1/resources/official-rule/').data
        self.assertEqual(result['source_url'], '')
        self.assertEqual(result['content'], '公开资料\n可阅读')
        self.assertEqual(result['provider'], '单位：校内')
        self.assertNotIn('private', str(result))
        self.resource.access_url = 'https://www.robomaster.com/zh-CN/robo/training-system#course'
        self.resource.save()
        self.assertTrue(self.client.get('/api/v1/resources/official-rule/').data['source_url'].endswith('training-system'))

    def test_options_and_filters_use_real_taxonomy(self):
        options = self.client.get('/api/v1/resources/options/').data
        self.assertEqual(options, {'categories': [{'code': 'rules', 'name': '竞赛规则'}],
                                  'directions': [{'code': 'robotics', 'name': '机器人'}], 'has_unclassified': False})
        self.assertEqual(self.client.get('/api/v1/resources/', {'category': 'rules', 'direction': 'robotics'}).data['count'], 1)
        self.client.force_authenticate(user=self.staff)
        self.assertTrue(self.client.get('/api/v1/resources/options/', {'preview': '1'}).data['has_unclassified'])
        result = self.client.get('/api/v1/resources/', {'preview': '1', 'category': 'unclassified'})
        self.assertEqual(result.data['count'], 1)
        self.assertIsNone(result.data['results'][0]['category'])

    def test_search_and_parameter_bounds(self):
        self.assertEqual(self.client.get('/api/v1/resources/', {'search': '规则正文'}).data['count'], 1)
        self.assertEqual(self.client.get('/api/v1/resources/', {'search': 'no-such-word'}).data['count'], 0)
        for params in ({'search': 'x' * 201}, {'category': 'x' * 65}, {'direction': 'x' * 65},
                       {'catalog_code': 'x' * 17}, {'page_size': 0}, {'page_size': 'abc'},
                       {'category': 'robotics'}, {'direction': 'rules'}, {'catalog_code': '2026999'}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get('/api/v1/resources/', params).status_code, 400)

    def test_pagination_caps_at_fifty_and_pages_are_disjoint(self):
        for number in range(55):
            self.make_resource(f'learning-{number:02}')
        response = self.client.get('/api/v1/resources/', {'page_size': 100})
        self.assertEqual(response.data['count'], 56)
        self.assertEqual(len(response.data['results']), 50)
        second = self.client.get('/api/v1/resources/', {'page_size': 100, 'page': 2})
        self.assertEqual(len(second.data['results']), 6)
        self.assertFalse({r['id'] for r in response.data['results']} & {r['id'] for r in second.data['results']})
        self.assertEqual(len(self.client.get('/api/v1/resources/').data['results']), 20)

    def test_http_read_never_accesses_remote_pages(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('No network during resource reads')), \
             patch('socket.create_connection', side_effect=AssertionError('No network during resource reads')):
            self.assertEqual(self.client.get('/api/v1/resources/').status_code, 200)
            self.assertEqual(self.client.get('/api/v1/resources/official-rule/').status_code, 200)
            self.assertEqual(self.client.get('/api/v1/resources/options/').status_code, 200)
