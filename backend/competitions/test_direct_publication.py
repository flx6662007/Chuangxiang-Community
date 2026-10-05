"""直接发布保留真实核验状态、日期与组队权限，不依赖外部网络。"""

from datetime import date, datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from governance.models import AdminAction

from .models import Competition, CompetitionSource, CompetitionTaxonomy
from .services import (
    publish_competition, publish_competition_direct, save_competition,
    save_source, withdraw_competition,
)


@override_settings(ROOT_URLCONF='competitions.test_api')
class DirectPublicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser(email='direct-editor@tongji.edu.cn', password='test-password')
        cls.category = CompetitionTaxonomy.objects.create(code='catalog', kind='category', name='目录赛事')

    def draft(self, code='direct-event', **fields):
        values = dict(
            code=code, title='测试赛事', edition='2026', summary='原通知摘要',
            description='原通知正文', registration_deadline=date(2026, 10, 15),
        )
        values.update(fields)
        competition = save_competition(Competition(**values), actor=self.actor)
        save_source(CompetitionSource(
            competition=competition, source_type='official', source_name='赛事官方通知',
            source_url='https://www.robomaster.com/zh-CN/robo/training-system', is_primary=True,
            source_published_on=date(2026, 9, 1),
        ), actor=self.actor)
        return competition

    def publish(self, competition, **kwargs):
        return publish_competition_direct(competition.pk, actor=self.actor, category=self.category, **kwargs)

    def test_direct_publication_preserves_dates_unverified_sources_and_closed_recruitment(self):
        competition = self.publish(self.draft())
        self.assertEqual(competition.publication_status, 'published')
        self.assertEqual(competition.publication_method, 'direct')
        self.assertEqual(competition.category, self.category)
        self.assertIsNone(competition.last_verified_at)
        self.assertEqual(competition.registration_deadline, date(2026, 10, 15))
        self.assertIsNone(competition.registration_deadline_at)
        self.assertFalse(competition.recruitment_enabled)
        self.assertFalse(competition.is_recruitment_open)
        source = competition.sources.get()
        self.assertIsNone(source.last_verified_at)
        self.assertEqual(source.source_published_on, date(2026, 9, 1))
        source.full_clean()
        source.source_url = 'https://127.0.0.1/private'
        with self.assertRaises(ValidationError):
            source.full_clean()
        action = AdminAction.objects.get(action='publish', competition=competition)
        self.assertEqual(action.changes['fields'], ['publication_method'])
        self.assertEqual(action.reason, '按项目决定直接发布')

    def test_anonymous_list_and_detail_include_unverified_source_without_claiming_verification(self):
        competition = self.publish(self.draft())
        response = self.client.get('/api/v1/competitions/', {'time_status': 'all'})
        self.assertEqual(response.status_code, 200)
        card = response.json()['results'][0]
        self.assertEqual(card['id'], competition.pk)
        self.assertEqual(card['publication_method'], 'direct')
        self.assertIsNone(card['last_verified_at'])
        self.assertIsNone(card['primary_source']['last_verified_at'])
        detail = self.client.get(f'/api/v1/competitions/{competition.pk}/').json()
        self.assertEqual(len(detail['sources']), 1)
        self.assertEqual(detail['sources'][0]['source_url'], competition.sources.get().source_url)
        self.assertEqual(detail['registration_deadline'], '2026-10-15')

    def test_publish_is_idempotent_without_changing_verified_records(self):
        competition = self.publish(self.draft())
        before = (competition.published_at, competition.updated_at)
        repeated = self.publish(competition)
        self.assertEqual((repeated.published_at, repeated.updated_at), before)
        self.assertEqual(AdminAction.objects.filter(action='publish', competition=competition).count(), 1)
        competition.sources.update(last_verified_at=timezone.now())
        verified = publish_competition(competition.pk, actor=self.actor)
        self.assertEqual(verified.publication_method, 'verified')
        self.assertIsNotNone(verified.last_verified_at)
        repeated = self.publish(verified)
        self.assertEqual(repeated.publication_method, 'verified')
        self.assertEqual(repeated.last_verified_at, verified.last_verified_at)

    def test_direct_does_not_forge_or_clear_existing_verification_timestamps(self):
        competition = self.draft()
        stamp = timezone.now()
        Competition.objects.filter(pk=competition.pk).update(last_verified_at=stamp)
        competition.sources.update(last_verified_at=stamp)
        published = self.publish(competition)
        self.assertEqual(published.last_verified_at, stamp)
        self.assertEqual(published.sources.get().last_verified_at, stamp)

    def test_verified_publication_still_requires_source_verification(self):
        competition = self.publish(self.draft())
        with self.assertRaises(ValidationError):
            publish_competition(competition.pk, actor=self.actor)
        competition.refresh_from_db()
        self.assertEqual(competition.publication_method, 'direct')
        self.assertIsNone(competition.last_verified_at)

    def test_does_not_republish_withdrawn_events(self):
        competition = self.publish(self.draft())
        withdraw_competition(competition.pk, actor=self.actor, reason='来源失效')
        with self.assertRaises(ValidationError):
            self.publish(competition)
        competition.refresh_from_db()
        self.assertEqual(competition.publication_status, 'withdrawn')

    def test_only_active_staff_with_competition_change_permission_can_publish(self):
        competition = self.draft()
        for staff in (False, True):
            user = get_user_model().objects.create_user(email=f'direct-{staff}@tongji.edu.cn', is_staff=staff)
            with self.assertRaises(PermissionDenied):
                publish_competition_direct(competition.pk, actor=user, category=self.category)
        user.user_permissions.add(Permission.objects.get(codename='change_competition'))
        user = get_user_model().objects.get(pk=user.pk)
        self.assertEqual(publish_competition_direct(
            competition.pk, actor=user, category=self.category,
        ).publication_status, 'published')

    def test_incomplete_content_or_missing_primary_source_rolls_back(self):
        for number, field in enumerate(('summary', 'description')):
            competition = self.draft(code=f'missing-{number}', **{field: ''})
            with self.assertRaises(ValidationError):
                self.publish(competition)
            competition.refresh_from_db()
            self.assertEqual(competition.publication_status, 'draft')
            self.assertIsNone(competition.published_at)
        competition = self.draft(code='missing-source')
        competition.sources.update(is_primary=False)
        with self.assertRaises(ValidationError):
            self.publish(competition)
        self.assertFalse(AdminAction.objects.filter(action='publish').exists())

    def test_unsafe_sources_and_registration_links_are_rejected(self):
        for number, url in enumerate((
            'https://127.0.0.1/notice', 'https://localhost/notice',
            'https://user:password@www.robomaster.com/notice',
            'https://www.robomaster.com/notice?token=private',
        )):
            competition = self.draft(code=f'unsafe-{number}')
            competition.sources.update(source_url=url)
            with self.assertRaises(ValidationError):
                self.publish(competition)
        competition = self.draft(code='unsafe-registration', registration_url='http://127.0.0.1/private')
        with self.assertRaises(ValidationError):
            self.publish(competition)

    def test_real_date_consistency_remains_required(self):
        competition = self.draft()
        Competition.objects.filter(pk=competition.pk).update(
            registration_deadline_at=datetime(2026, 10, 16, 1, tzinfo=dt_timezone.utc),
            registration_deadline_timezone='Asia/Shanghai',
        )
        with self.assertRaises(ValidationError):
            self.publish(competition)

    def test_database_only_relaxes_verification_for_direct_publication(self):
        competition = self.draft()
        values = dict(publication_status='published', published_at=timezone.now(), category=self.category)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Competition.objects.filter(pk=competition.pk).update(**values)
        Competition.objects.filter(pk=competition.pk).update(**values, publication_method='direct')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Competition.objects.filter(pk=competition.pk).update(publication_method='anything')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Competition.objects.filter(pk=competition.pk).update(summary='')
