"""从实际 Admin 表单到公开 API 的端到端服务器测试。"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import include, path

from .models import Competition, CompetitionSource, CompetitionTaxonomy

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/competitions/', include('competitions.urls')),
]


@override_settings(ROOT_URLCONF='competitions.test_admin')
class CompetitionAdminWorkflowTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(email='admin-demo@tongji.edu.cn', password='test-password')
        self.client.force_login(self.actor)
        self.category = CompetitionTaxonomy.objects.create(code='demo', kind='category', name='演示分类')

    def test_admin_draft_source_publish_edit_withdraw_workflow(self):
        data = {
            'code': 'admin-demo', 'title': 'Admin 演示赛事', 'edition': '2026',
            'summary': '演示简介', 'description': '演示详情', 'category': self.category.pk,
            'level': 'unknown', 'participation_type': 'unknown', '_save': '保存',
        }
        response = self.client.post('/admin/competitions/competition/add/', data)
        self.assertEqual(response.status_code, 302)
        competition = Competition.objects.get(code='admin-demo')
        self.assertEqual(competition.publication_status, 'draft')
        self.assertEqual(self.client.get(f'/api/v1/competitions/{competition.pk}/').status_code, 404)
        response = self.client.post('/admin/competitions/competitionsource/add/', {
            'competition': competition.pk, 'source_type': 'official', 'source_name': '虚构官方通知',
            'source_url': 'https://example.org/admin-demo', 'is_primary': 'on', 'verified': 'on', '_save': '保存',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(competition.sources.get().last_verified_at)
        response = self.client.post('/admin/competitions/competition/', {
            'action': 'verify_and_publish', '_selected_action': [competition.pk], 'index': '0',
        })
        self.assertEqual(response.status_code, 302)
        competition.refresh_from_db()
        self.assertEqual(competition.publication_status, 'published')
        self.assertEqual(self.client.get(f'/api/v1/competitions/{competition.pk}/').status_code, 200)
        first = competition.published_at
        before = competition.updated_at
        data['summary'] = '更正后的简介'
        data['publication_status'] = 'draft'  # 伪造只读系统字段不会改变发布状态。
        response = self.client.post(f'/admin/competitions/competition/{competition.pk}/change/', data)
        self.assertEqual(response.status_code, 302)
        competition.refresh_from_db()
        self.assertEqual(competition.summary, '更正后的简介')
        self.assertEqual(competition.published_at, first)
        self.assertGreater(competition.updated_at, before)
        response = self.client.post('/admin/competitions/competition/', {
            'action': 'withdraw_selected', '_selected_action': [competition.pk],
            'withdrawal_reason': '演示内容停止展示', 'index': '0',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(f'/api/v1/competitions/{competition.pk}/').status_code, 404)

    def test_invalid_publication_shows_admin_message_without_server_error(self):
        competition = Competition.objects.create(code='incomplete', title='不完整草稿', edition='2026')
        response = self.client.post('/admin/competitions/competition/', {
            'action': 'verify_and_publish', '_selected_action': [competition.pk], 'index': '0',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        competition.refresh_from_db()
        self.assertEqual(competition.publication_status, 'draft')
        self.assertContains(response, '发布前')

    def test_admin_add_replacement_primary_source_then_publish(self):
        competition = Competition.objects.create(
            code='replace-primary', title='替换主来源演示', edition='2026',
            summary='演示简介', description='演示详情', category=self.category,
        )
        source_data = {
            'competition': competition.pk, 'source_type': 'official', 'source_name': '原始通知',
            'source_url': 'https://example.org/original', 'is_primary': 'on',
            'verified': 'on', '_save': '保存',
        }
        self.assertEqual(self.client.post('/admin/competitions/competitionsource/add/', source_data).status_code, 302)
        original = competition.sources.get()
        source_data.update(source_name='修订通知', source_url='https://example.org/replacement')
        response = self.client.post('/admin/competitions/competitionsource/add/', source_data)
        self.assertEqual(response.status_code, 302)
        original.refresh_from_db()
        self.assertFalse(original.is_primary)
        self.assertIsNotNone(original.last_verified_at)
        replacement = competition.sources.get(is_primary=True)
        self.assertEqual(replacement.source_url, source_data['source_url'])
        self.assertIsNotNone(replacement.last_verified_at)
        self.assertEqual(competition.sources.count(), 2)
        self.client.post('/admin/competitions/competition/', {
            'action': 'verify_and_publish', '_selected_action': [competition.pk], 'index': '0',
        })
        detail = self.client.get(f'/api/v1/competitions/{competition.pk}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['primary_source']['id'], replacement.pk)

    def test_invalid_replacement_source_preserves_existing_primary(self):
        competition = Competition.objects.create(code='invalid-replacement', title='来源校验演示', edition='2026')
        original = CompetitionSource.objects.create(
            competition=competition, source_type='official', source_name='原始通知',
            source_url='https://example.org/original', is_primary=True,
        )
        response = self.client.post('/admin/competitions/competitionsource/add/', {
            'competition': competition.pk, 'source_type': 'official', 'source_name': '错误通知',
            'source_url': 'javascript:alert(1)', 'is_primary': 'on', 'verified': 'on', '_save': '保存',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('source_url', response.context['adminform'].form.errors)
        original.refresh_from_db()
        self.assertTrue(original.is_primary)
        self.assertEqual(competition.sources.count(), 1)
