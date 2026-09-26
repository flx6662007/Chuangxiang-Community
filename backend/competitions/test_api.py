"""公开字段、分页及查询数量验收；所有赛事和邮箱均为虚构。"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import include, path
from django.utils import timezone

from .models import Competition, CompetitionSource, CompetitionTaxonomy
from .serializers import CompetitionDetailSerializer, CompetitionListSerializer, PublicSourceSerializer

urlpatterns = [path('api/v1/competitions/', include('competitions.urls'))]


@override_settings(ROOT_URLCONF='competitions.test_api')
class CompetitionAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = CompetitionTaxonomy.objects.create(code='engineering', kind='category', name='工程')
        cls.tag = CompetitionTaxonomy.objects.create(code='robot', kind='tag', name='机器人')
        cls.actor = get_user_model().objects.create_user(email='demo-editor@tongji.edu.cn', password='test-password')
        cls.public = []
        for i in range(24):
            item = Competition.objects.create(
                code=f'demo-{i}', title=f'虚构机器人赛事 {i}', edition='2026',
                summary='演示工程竞赛', description='测试详情', category=cls.category,
                organizer='虚构工程协会', registration_deadline=date(2020, 1, 1),
                created_by=cls.actor, recruitment_note='内部资料', withdrawal_reason='内部原因',
            )
            item.tags.add(cls.tag)
            CompetitionSource.objects.create(
                competition=item, source_type='official', source_name='演示来源',
                source_url='https://example.org/notice', is_primary=True,
                last_verified_at=timezone.now(),
            )
            item.publication_status = 'published'
            item.published_at = timezone.now() - timedelta(days=24 - i)
            item.last_verified_at = timezone.now()
            item.full_clean()
            item.save()
            cls.public.append(item)
        cls.draft = Competition.objects.create(code='draft', title='草稿', edition='2026')
        cls.withdrawn = Competition.objects.create(
            code='withdrawn', title='下架', edition='2026', publication_status='withdrawn',
            published_at=timezone.now(), withdrawal_reason='内部原因',
        )

    def test_guest_list_has_public_only_stable_order_and_pagination(self):
        response = self.client.get('/api/v1/competitions/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(set(payload), {'count', 'next', 'previous', 'results'})
        self.assertEqual(payload['count'], 24)
        self.assertEqual(len(payload['results']), 20)
        self.assertEqual(payload['results'][0]['id'], self.public[-1].pk)
        self.assertIsNone(payload['previous'])
        self.assertIn('page=2', payload['next'])
        self.assertEqual(len(self.client.get('/api/v1/competitions/?page=2').json()['results']), 4)

    def test_field_whitelists_and_source_privacy(self):
        card = self.client.get('/api/v1/competitions/').json()['results'][0]
        self.assertEqual(set(card), set(CompetitionListSerializer.Meta.fields))
        detail = self.client.get(f'/api/v1/competitions/{self.public[0].pk}/').json()
        self.assertEqual(set(detail), set(CompetitionDetailSerializer.Meta.fields))
        self.assertEqual(set(detail['sources'][0]), set(PublicSourceSerializer.Meta.fields))
        for field in ('withdrawal_reason', 'recruitment_note', 'created_by', 'updated_by', 'created_at'):
            self.assertNotIn(field, detail)
        self.assertIsNone(detail['registration_deadline_at'])
        self.assertEqual(detail['registration_deadline_timezone'], '')
        self.assertEqual(detail['registration_deadline'], '2020-01-01')

    def test_unpublished_and_missing_detail_are_404(self):
        for pk in (self.draft.pk, self.withdrawn.pk, 99999):
            self.assertEqual(self.client.get(f'/api/v1/competitions/{pk}/').status_code, 404)

    def test_search_and_category_filters(self):
        for search in ('机器人', '工程竞赛', '工程协会'):
            self.assertEqual(self.client.get('/api/v1/competitions/', {'search': search}).json()['count'], 24)
        self.assertEqual(self.client.get('/api/v1/competitions/?search=不存在').json()['count'], 0)
        self.assertEqual(self.client.get('/api/v1/competitions/?category=engineering').json()['count'], 24)
        self.assertEqual(self.client.get('/api/v1/competitions/?category=unknown').json()['count'], 0)

    def test_page_size_bounds_and_bad_inputs(self):
        self.assertEqual(len(self.client.get('/api/v1/competitions/?page_size=1').json()['results']), 1)
        self.assertEqual(len(self.client.get('/api/v1/competitions/?page_size=500').json()['results']), 24)
        for value in ('0', '-1', 'x'):
            self.assertEqual(self.client.get('/api/v1/competitions/', {'page_size': value}).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/competitions/?page=999').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/competitions/', {'search': 'x' * 201}).status_code, 400)

    def test_categories_and_options_exclude_inactive_and_separate_kinds(self):
        CompetitionTaxonomy.objects.create(code='disabled', name='停用分类', kind='category', is_active=False)
        CompetitionTaxonomy.objects.create(code='demo-r1-category-1', name='【虚构样例】分类', kind='category')
        response = self.client.get('/api/v1/competitions/categories/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{'id': self.category.pk, 'code': 'engineering', 'name': '工程'}])
        options = self.client.get('/api/v1/competitions/options/').json()
        self.assertEqual([row['code'] for row in options['tags']], ['robot'])
        self.assertIn({'code': 'unknown', 'name': '未注明'}, options['levels'])

    def test_known_seed_samples_are_not_public_but_history_is_preserved(self):
        event = self.public[0]
        Competition.objects.filter(pk=event.pk).update(code='demo-r1-public-001', title='【虚构样例】演示')
        self.assertEqual(self.client.get('/api/v1/competitions/').json()['count'], 23)
        self.assertEqual(self.client.get(f'/api/v1/competitions/{event.pk}/').status_code, 404)
        self.assertTrue(Competition.objects.filter(pk=event.pk, publication_status='published').exists())

    def test_recruitment_filter_requires_all_event_conditions(self):
        event = self.public[0]
        event.participation_type = 'team'
        event.recruitment_enabled = True
        event.recruitment_deadline = timezone.now() + timedelta(days=1)
        event.full_clean()
        event.save()
        result = self.client.get('/api/v1/competitions/?recruitment_open=true').json()
        self.assertEqual([row['id'] for row in result['results']], [event.pk])
        self.assertEqual(self.client.get('/api/v1/competitions/?recruitment_open=false').json()['count'], 23)
        self.assertEqual(self.client.get('/api/v1/competitions/?recruitment_open=maybe').status_code, 400)

    def test_available_events_precede_expired_and_source_date_precedes_fetch_order(self):
        current = self.public[0]
        Competition.objects.filter(pk=current.pk).update(registration_deadline=timezone.localdate() + timedelta(days=7))
        old_notice = self.public[1]
        old_notice.sources.update(source_published_on=timezone.localdate())
        result = self.client.get('/api/v1/competitions/').json()['results']
        self.assertEqual(result[0]['id'], current.pk)
        self.assertEqual(result[1]['id'], old_notice.pk)

    def test_read_only_and_no_authentication_overhead(self):
        self.assertEqual(self.client.post('/api/v1/competitions/', {}).status_code, 405)
        self.assertEqual(self.client.delete(f'/api/v1/competitions/{self.public[0].pk}/').status_code, 405)
        self.client.force_login(self.actor)
        # count + 主查询（含分类）+ 标签 + 来源；即使带登录 cookie 也不读取会话/账号。
        with self.assertNumQueries(4):
            response = self.client.get('/api/v1/competitions/')
            self.assertEqual(response.status_code, 200)
        with self.assertNumQueries(3):
            self.assertEqual(self.client.get(f'/api/v1/competitions/{self.public[0].pk}/').status_code, 200)
