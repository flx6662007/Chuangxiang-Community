"""独立测试库中的赛事时效边界；不删除历史内容或变更招募资格。"""

from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Competition, CompetitionSource, CompetitionTaxonomy


@override_settings(ROOT_URLCONF='competitions.test_api')
class CompetitionTimelinessTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 28, 4, tzinfo=dt_timezone.utc)
        clock = patch('competitions.timeliness.timezone.now', return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)
        self.today = timezone.localdate(self.now)
        self.category = CompetitionTaxonomy.objects.create(code='timing-engineering', kind='category', name='工程技术')
        self.sequence = 0

    def event(self, **fields):
        self.sequence += 1
        values = dict(
            code=f'timing-{self.sequence}', title=f'测试工程赛事 {self.sequence}', edition='2026',
            summary='赛事时效测试', description='仅供独立测试', category=self.category,
            publication_status='published', published_at=self.now, last_verified_at=self.now,
        )
        values.update(fields)
        item = Competition.objects.create(**values)
        CompetitionSource.objects.create(
            competition=item, source_type='official', source_name='测试来源',
            source_url='https://example.org/timing', is_primary=True, last_verified_at=self.now,
        )
        return item

    def listing(self, **params):
        response = self.client.get('/api/v1/competitions/', params)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def detail(self, item):
        response = self.client.get(f'/api/v1/competitions/{item.pk}/')
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_default_excludes_only_known_expiry_and_retains_unknown(self):
        current = self.event(registration_deadline=self.today + timedelta(days=1))
        unknown = self.event()
        expired = self.event(registration_deadline=self.today - timedelta(days=1))
        rows = self.listing()['results']
        self.assertEqual([row['id'] for row in rows], [current.pk, unknown.pk])
        self.assertEqual([row['deadline_status'] for row in rows], ['open', 'unknown'])
        self.assertIn('未明确', rows[1]['deadline_status_label'])
        self.assertEqual([row['id'] for row in self.listing(time_status='expired')['results']], [expired.pk])
        self.assertEqual(self.listing(time_status='all')['count'], 3)

    def test_expired_registration_is_not_overridden_by_submission_or_recruitment(self):
        event = self.event(
            registration_deadline=self.today - timedelta(days=1),
            submission_deadline=self.today + timedelta(days=30),
            participation_type='team', recruitment_enabled=True,
            recruitment_deadline=self.now + timedelta(days=30), recruitment_note='测试已核验招募期限',
        )
        self.assertEqual(self.listing()['count'], 0)
        row = self.detail(event)
        self.assertEqual(row['deadline_kind'], 'registration')
        self.assertEqual(row['deadline_status'], 'closed')
        self.assertEqual(row['deadline_status_label'], '报名已截止')
        self.assertTrue(row['is_recruitment_open'])
        self.assertEqual(self.listing(recruitment_open='true')['count'], 0)
        self.assertEqual(self.listing(time_status='all', recruitment_open='true')['count'], 1)
        event.refresh_from_db()
        self.assertEqual(event.publication_status, 'published')
        self.assertTrue(event.recruitment_enabled)

    def test_future_registration_wins_over_expired_submission(self):
        event = self.event(
            registration_deadline=self.today + timedelta(days=1),
            submission_deadline=self.today - timedelta(days=1),
        )
        row = self.listing()['results'][0]
        self.assertEqual(row['id'], event.pk)
        self.assertEqual(row['deadline_status'], 'open')
        self.assertEqual(row['deadline_kind'], 'registration')

    def test_submission_fallback_does_not_claim_registration_is_open(self):
        current = self.event(submission_deadline=self.today + timedelta(days=1))
        expired = self.event(submission_deadline=self.today - timedelta(days=1))
        row = self.listing()['results'][0]
        self.assertEqual(row['id'], current.pk)
        self.assertEqual(row['deadline_kind'], 'submission')
        self.assertIn('作品提交未截止', row['deadline_status_label'])
        self.assertIn('报名时间未明确', row['deadline_status_label'])
        self.assertNotIn('报名中', row['deadline_status_label'])
        self.assertEqual(self.detail(expired)['deadline_status_label'], '作品提交已截止')

    def test_date_only_today_stays_current_without_inventing_cutoff_hour(self):
        event = self.event(registration_deadline=self.today)
        row = self.listing()['results'][0]
        self.assertEqual(row['id'], event.pk)
        self.assertIn('今日截止', row['deadline_status_label'])
        self.assertIn('时刻以原文为准', row['deadline_status_label'])
        self.assertIsNone(row['registration_deadline_at'])

    def test_precise_instants_use_exact_boundary_and_override_date(self):
        for field in ('registration', 'submission'):
            for seconds, expected in ((-1, 'closed'), (0, 'closed'), (1, 'open')):
                with self.subTest(field=field, seconds=seconds):
                    instant = self.now + timedelta(seconds=seconds)
                    event = self.event(**{
                        field + '_deadline': self.today,
                        field + '_deadline_at': instant,
                        field + '_deadline_timezone': 'Asia/Shanghai',
                    })
                    self.assertEqual(self.detail(event)['deadline_status'], expected)
        self.assertEqual(self.listing()['count'], 2)
        self.assertEqual(self.listing(time_status='expired')['count'], 4)

    def test_recruitment_deadline_alone_does_not_establish_event_time(self):
        event = self.event(
            participation_type='team', recruitment_enabled=True,
            recruitment_deadline=self.now + timedelta(days=3), recruitment_note='测试招募依据',
        )
        row = self.detail(event)
        self.assertTrue(row['is_recruitment_open'])
        self.assertEqual(row['deadline_status'], 'unknown')
        self.assertEqual(row['deadline_kind'], 'unknown')

    def test_filters_and_pagination_preserve_selected_time_status(self):
        for _ in range(3):
            self.event(registration_deadline=self.today - timedelta(days=1))
        payload = self.listing(time_status='expired', category=self.category.code, search='工程', page_size=2)
        self.assertEqual(payload['count'], 3)
        self.assertEqual(len(payload['results']), 2)
        self.assertIn('time_status=expired', payload['next'])
        self.assertEqual(len(self.listing(time_status='expired', page_size=2, page=2)['results']), 1)

    def test_bad_time_status_is_rejected_and_detail_does_not_filter_history(self):
        for value in ('', 'open', 'CURRENT', 'unknown'):
            self.assertEqual(self.client.get('/api/v1/competitions/', {'time_status': value}).status_code, 400)
        event = self.event(registration_deadline=self.today - timedelta(days=1))
        self.assertEqual(self.client.get(f'/api/v1/competitions/{event.pk}/?time_status=current').status_code, 200)
