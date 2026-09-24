from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from .models import Competition, CompetitionSource, CompetitionTaxonomy


class CompetitionModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = CompetitionTaxonomy.objects.create(code='demo-category', kind='category', name='演示分类')
        cls.tag = CompetitionTaxonomy.objects.create(code='demo-tag', kind='tag', name='演示标签')

    def draft(self, code='demo-2026', **kwargs):
        competition = Competition(code=code, title='演示赛事', edition='2026 年度', **kwargs)
        competition.full_clean()
        competition.save()
        return competition

    def source(self, competition, **kwargs):
        values = dict(
            competition=competition, source_type='official', source_name='演示官方来源',
            source_url='https://example.org/demo', is_primary=True, last_verified_at=timezone.now(),
        )
        values.update(kwargs)
        source = CompetitionSource(**values)
        source.full_clean()
        source.save()
        return source

    def prepare_publication(self, competition):
        competition.category = self.category
        competition.summary = '虚构数据，仅供测试。'
        competition.description = '虚构赛事详细说明。'
        competition.publication_status = 'published'
        competition.published_at = timezone.now()
        competition.last_verified_at = timezone.now()

    def published(self, **kwargs):
        competition = self.draft(**kwargs)
        self.source(competition)
        self.prepare_publication(competition)
        competition.full_clean()
        competition.save()
        return competition

    def test_minimal_draft_allows_missing_dates(self):
        competition = self.draft()
        self.assertIsNone(competition.registration_deadline)
        self.assertIsNone(competition.published_at)
        self.assertFalse(competition.is_recruitment_open)

    def test_database_rejects_empty_identity_and_invalid_values(self):
        for fields in (
            {'title': ' \t '}, {'edition': ''}, {'code': 'UPPER'},
            {'publication_status': 'archived'}, {'level': 'fake'},
            {'team_size_min': 0}, {'team_size_min': 5, 'team_size_max': 2},
            {'participation_type': 'individual', 'team_size_max': 1},
        ):
            values = dict(code='demo-2026', title='演示', edition='2026')
            values.update(fields)
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                Competition.objects.create(**values)

    def test_date_only_does_not_invent_time_or_require_chronology(self):
        competition = self.draft(registration_deadline=date(2026, 10, 15), submission_deadline=date(2026, 10, 1))
        self.assertIsNone(competition.registration_deadline_at)
        self.assertEqual(competition.registration_deadline_timezone, '')

    def test_exact_time_matches_source_date_after_conversion(self):
        competition = self.draft(
            registration_deadline=date(2026, 10, 16),
            registration_deadline_at=datetime(2026, 10, 15, 18, tzinfo=dt_timezone.utc),
            registration_deadline_timezone='Asia/Shanghai',
        )
        competition.registration_deadline = date(2026, 10, 15)
        with self.assertRaises(ValidationError):
            competition.full_clean()

    def test_invalid_timezone_and_naive_time_rejected(self):
        for zone in ('Mars/Olympus', '+25:00', '+08:99'):
            with self.subTest(zone=zone), self.assertRaises(ValidationError):
                self.draft(registration_deadline=date(2026, 10, 15), registration_deadline_timezone=zone)
        with self.assertRaises(ValidationError):
            self.draft(
                registration_deadline=date(2026, 10, 15),
                registration_deadline_at=datetime(2026, 10, 15, 18), registration_deadline_timezone='+08:00',
            )

    def test_database_rejects_incomplete_date_time_pairs(self):
        competition = self.draft()
        for fields in (
            {'registration_deadline_timezone': 'Asia/Shanghai'},
            {'registration_deadline_at': timezone.now()},
            {'registration_deadline': date(2026, 10, 15), 'registration_deadline_at': timezone.now()},
        ):
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                Competition.objects.filter(pk=competition.pk).update(**fields)

    def test_publication_requires_verified_primary_source(self):
        competition = self.draft()
        self.prepare_publication(competition)
        with self.assertRaises(ValidationError):
            competition.full_clean()
        self.source(competition, last_verified_at=None)
        with self.assertRaises(ValidationError):
            competition.full_clean()
        source = competition.sources.get()
        source.last_verified_at = timezone.now()
        source.save()
        competition.full_clean()
        competition.save()
        self.assertIsNone(competition.registration_deadline)

    def test_multiple_primary_sources_rejected_by_database(self):
        competition = self.draft()
        self.source(competition)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CompetitionSource.objects.create(
                competition=competition, source_type='campus', source_name='校内来源',
                source_url='https://example.org/campus', is_primary=True,
            )

    def test_source_url_can_be_reused_for_another_edition(self):
        self.source(self.draft('demo-2026'))
        self.source(self.draft('demo-2027'))
        self.assertEqual(CompetitionSource.objects.count(), 2)

    def test_source_only_accepts_http_and_https(self):
        with self.assertRaises(ValidationError):
            self.source(self.draft(), source_url='ftp://example.org/demo')

    def test_campus_arrangements_require_campus_source(self):
        competition = self.published()
        competition.campus_arrangements = '演示校内选拔'
        with self.assertRaises(ValidationError):
            competition.full_clean()
        self.source(competition, source_type='campus', is_primary=False)
        competition.full_clean()

    def test_category_cannot_be_a_tag_or_new_inactive_selection(self):
        competition = self.draft()
        competition.category = self.tag
        with self.assertRaises(ValidationError):
            competition.full_clean()
        self.category.is_active = False
        self.category.save()
        competition.category = self.category
        with self.assertRaises(ValidationError):
            competition.full_clean()

    def test_tag_relation_rejects_categories_and_inactive_tags_in_both_directions(self):
        competition = self.draft()
        with self.assertRaises(ValidationError), transaction.atomic():
            competition.tags.add(self.category)
        with self.assertRaises(ValidationError), transaction.atomic():
            self.category.tagged_competitions.add(competition)
        competition.tags.add(self.tag)
        self.tag.is_active = False
        self.tag.save()
        self.assertEqual(list(competition.tags.all()), [self.tag])
        other = self.draft('another-2026')
        with self.assertRaises(ValidationError), transaction.atomic():
            other.tags.add(self.tag)

    def test_used_taxonomy_and_published_competition_cannot_be_deleted(self):
        competition = self.published()
        competition.tags.add(self.tag)
        with self.assertRaises(ProtectedError), transaction.atomic():
            CompetitionTaxonomy.objects.filter(pk=self.tag.pk).delete()
        with self.assertRaises(ProtectedError), transaction.atomic():
            Competition.objects.filter(pk=competition.pk).delete()

    def test_draft_deletion_cascades_sources(self):
        competition = self.draft()
        self.source(competition)
        competition.delete()
        self.assertEqual(CompetitionSource.objects.count(), 0)

    def test_first_publication_time_and_codes_are_fixed(self):
        competition = self.published()
        competition.published_at += timedelta(days=1)
        with self.assertRaises(ValidationError):
            competition.full_clean()
        competition.refresh_from_db()
        competition.code = 'changed-2026'
        with self.assertRaises(ValidationError):
            competition.full_clean()
        self.tag.kind = 'category'
        with self.assertRaises(ValidationError):
            self.tag.full_clean()

    def test_withdrawal_requires_reason_and_closed_recruitment(self):
        competition = self.published(participation_type='team')
        competition.publication_status = 'withdrawn'
        with self.assertRaises(ValidationError):
            competition.full_clean()
        competition.withdrawal_reason = '演示下架原因'
        competition.full_clean()
        competition.save()
        self.assertIsNotNone(competition.published_at)

    def test_recruitment_requires_public_team_with_future_deadline_and_reason(self):
        competition = self.published(participation_type='team')
        competition.recruitment_enabled = True
        with self.assertRaises(ValidationError):
            competition.full_clean()
        competition.recruitment_deadline = timezone.now() + timedelta(days=10)
        competition.recruitment_note = '演示已核验期限'
        competition.full_clean()
        competition.save()
        self.assertTrue(competition.is_recruitment_open)
        with patch('competitions.models.timezone.now', return_value=competition.recruitment_deadline):
            self.assertFalse(competition.is_recruitment_open)
        competition.publication_status = 'withdrawn'
        competition.withdrawal_reason = '暂停'
        with self.assertRaises(ValidationError):
            competition.full_clean()

    def test_expired_registration_stays_public(self):
        competition = self.published(registration_deadline=date(2020, 1, 1))
        competition.refresh_from_db()
        self.assertEqual(competition.publication_status, 'published')
