"""Directory API protects unpublished counts while keeping directory identity visible."""

from django.test import TestCase

from curation.models import DocumentLink
from curation.test_api import LibraryAPIFixtures

from .models import CatalogBinding


class CatalogAPITests(LibraryAPIFixtures, TestCase):
    def test_public_counts_and_detail_only_include_visible_editions_documents_resources(self):
        response = self.client.get('/api/v1/competition-catalog/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        row = response.data['results'][0]
        self.assertEqual(row['code'], '2026001')
        self.assertEqual((row['competition_count'], row['resource_count'], row['document_count']), (1, 1, 1))
        detail = self.client.get('/api/v1/competition-catalog/2026001/')
        self.assertEqual(len(detail.data['competitions']), 1)
        self.assertEqual(detail.data['competitions'][0]['id'], self.public_competition.pk)
        self.assertEqual(detail.data['competitions'][0]['url'], f'/information/competitions/{self.public_competition.pk}')
        self.assertEqual(detail['Cache-Control'], 'private, no-store')
        self.assertNotIn('private', str(detail.data))
        empty = self.client.get('/api/v1/competition-catalog/2026002/').data
        self.assertEqual((empty['competition_count'], empty['resource_count'], empty['document_count']), (0, 0, 0))

    def test_preview_permissions_and_draft_counts_do_not_change_public_counts(self):
        for user in (None, self.student, self.limited):
            self.client.force_authenticate(user=user)
            for endpoint in ('', '2026001/'):
                with self.subTest(user=user, endpoint=endpoint):
                    self.assertEqual(self.client.get('/api/v1/competition-catalog/' + endpoint,
                                                     {'preview': 'true'}).status_code, 403)
        self.client.force_authenticate(user=self.staff)
        preview = self.client.get('/api/v1/competition-catalog/2026001/', {'preview': '1'})
        self.assertEqual(preview.status_code, 200)
        self.assertEqual((preview.data['competition_count'], preview.data['resource_count'], preview.data['document_count']), (2, 2, 2))
        draft = next(row for row in preview.data['competitions'] if row['publication_status'] == 'draft')
        self.assertEqual(draft['url'], '')
        self.assertNotIn('withdrawn', {row['publication_status'] for row in preview.data['competitions']})
        public = self.client.get('/api/v1/competition-catalog/2026001/').data
        self.assertEqual((public['competition_count'], public['resource_count'], public['document_count']), (1, 1, 1))
        self.staff.is_active = False
        self.assertEqual(self.client.get('/api/v1/competition-catalog/', {'preview': '1'}).status_code, 403)

    def test_counts_move_with_current_revision_and_resource_deduplication(self):
        self.make_document('second-public-guide', 'approved', self.catalog, self.public_resource)
        row = self.client.get('/api/v1/competition-catalog/2026001/').data
        self.assertEqual((row['resource_count'], row['document_count']), (1, 2))
        revision = self.make_revision(self.public_document, 2, self.second_catalog, self.public_resource)
        self.public_document.current_revision = revision
        self.public_document.save()
        old = self.client.get('/api/v1/competition-catalog/2026001/').data
        new = self.client.get('/api/v1/competition-catalog/2026002/').data
        self.assertEqual((old['competition_count'], old['resource_count'], old['document_count']), (1, 1, 1))
        self.assertEqual((new['competition_count'], new['resource_count'], new['document_count']), (0, 1, 1))

    def test_hidden_target_removes_document_count_but_keeps_visible_resource_count(self):
        DocumentLink.objects.create(revision=self.public_document.current_revision, resource=self.draft_resource)
        row = self.client.get('/api/v1/competition-catalog/2026001/').data
        self.assertEqual((row['competition_count'], row['resource_count'], row['document_count']), (1, 1, 0))

    def test_published_resource_count_does_not_require_knowledge_body_approval(self):
        self.public_document.review_status = 'draft'
        self.public_document.save()
        DocumentLink.objects.create(revision=self.public_document.current_revision, competition=self.draft_competition)
        row = self.client.get('/api/v1/competition-catalog/2026001/').data
        self.assertEqual((row['competition_count'], row['resource_count'], row['document_count']), (1, 1, 0))
        resources = self.client.get('/api/v1/resources/', {'catalog_code': '2026001'}).data
        self.assertEqual(resources['count'], row['resource_count'])
        self.assertEqual(resources['results'][0]['id'], self.public_resource.code)
        self.assertEqual(self.client.get('/api/v1/knowledge-documents/').data['count'], 0)

    def test_inactive_unknown_and_demo_editions_are_not_visible(self):
        self.assertEqual(self.client.get('/api/v1/competition-catalog/2026003/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/competition-catalog/9999999/').status_code, 404)
        demo = self.make_competition('demo-test')
        CatalogBinding.objects.create(entry=self.catalog, competition=demo, basis='测试')
        self.assertEqual(self.client.get('/api/v1/competition-catalog/2026001/').data['competition_count'], 1)

    def test_catalog_source_and_text_are_sanitized(self):
        self.catalog.source_url = 'https://www.tongji.edu.cn/private?token=secret'
        self.catalog.departments = ['<b>测试学院</b>\n邮箱：private@tongji.edu.cn']
        self.catalog.save()
        result = self.client.get('/api/v1/competition-catalog/2026001/').data
        self.assertEqual(result['source_url'], '')
        self.assertEqual(result['departments'], [])
        self.assertNotIn('private', str(result))

    def test_search_grade_page_limits_and_invalid_parameters(self):
        self.assertEqual(self.client.get('/api/v1/competition-catalog/', {'search': '数学'}).data['count'], 1)
        self.assertEqual(self.client.get('/api/v1/competition-catalog/', {'search': '2026001'}).data['count'], 1)
        self.assertEqual(self.client.get('/api/v1/competition-catalog/', {'grade': 'B'}).data['count'], 1)
        for params in ({'search': 'x' * 201}, {'grade': 'x' * 9}, {'preview': 'yes'},
                       {'page_size': 0}, {'page_size': 'abc'}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get('/api/v1/competition-catalog/', params).status_code, 400)
        for number in range(51):
            self.make_catalog(f'2026{number + 100:03}')
        result = self.client.get('/api/v1/competition-catalog/', {'page_size': 100})
        self.assertEqual(result.data['count'], 53)
        self.assertEqual(len(result.data['results']), 50)
        second = self.client.get('/api/v1/competition-catalog/', {'page_size': 100, 'page': 2})
        self.assertEqual(len(second.data['results']), 3)
        self.assertEqual(len(self.client.get('/api/v1/competition-catalog/').data['results']), 20)
        self.assertFalse({row['code'] for row in result.data['results']} & {row['code'] for row in second.data['results']})
