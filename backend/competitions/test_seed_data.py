from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .models import Competition, CompetitionSource, CompetitionTaxonomy


@override_settings(DEBUG=True)
class DemoDataTests(TestCase):
    def seed(self, **options):
        call_command('seed_demo_data', stdout=StringIO(), **options)

    def snapshot(self):
        return {
            model._meta.label: list(model.objects.order_by('pk').values())
            for model in (get_user_model(), Competition, CompetitionSource, CompetitionTaxonomy, Competition.tags.through)
        }

    def test_default_data_covers_publication_dates_relations_and_disabled_users(self):
        self.seed()
        self.assertEqual(Competition.objects.filter(publication_status='published').count(), 25)
        self.assertEqual(Competition.objects.filter(publication_status='draft').count(), 2)
        self.assertEqual(Competition.objects.filter(publication_status='withdrawn').count(), 1)
        self.assertEqual(CompetitionTaxonomy.objects.count(), 6)
        self.assertEqual(CompetitionSource.objects.count(), 30)
        self.assertEqual(Competition.tags.through.objects.count(), 26)
        self.assertEqual(get_user_model().objects.count(), 3)
        for user in get_user_model().objects.all():
            self.assertFalse(user.has_usable_password())
            self.assertFalse(user.is_active or user.is_staff or user.is_superuser)
            user.full_clean()
        for competition in Competition.objects.all():
            competition.full_clean()
            if competition.publication_status != 'draft':
                self.assertEqual(competition.sources.filter(is_primary=True).count(), 1)
        for source in CompetitionSource.objects.all():
            source.full_clean()
            self.assertTrue(source.source_url.startswith('https://example.org/'))
            self.assertIsNone(source.fetched_at)
        unknown = Competition.objects.get(code='demo-r1-public-001')
        self.assertIsNone(unknown.registration_deadline)
        day_only = Competition.objects.get(code='demo-r1-public-002')
        self.assertIsNotNone(day_only.registration_deadline)
        self.assertIsNone(day_only.registration_deadline_at)
        self.assertTrue(Competition.objects.get(code='demo-r1-public-003').is_recruitment_open)
        expired = Competition.objects.get(code='demo-r1-public-004')
        self.assertLess(expired.registration_deadline, expired.published_at.date())
        self.assertEqual(expired.publication_status, 'published')

    def test_repeated_import_preserves_all_values_and_manual_edits(self):
        self.seed(published_count=6)
        competition = Competition.objects.get(code='demo-r1-public-001')
        competition.summary = '本地人工调整的样例简介'
        competition.full_clean()
        competition.save()
        before = self.snapshot()
        self.seed(published_count=6)
        self.assertEqual(self.snapshot(), before)

    def test_larger_count_adds_only_missing_competitions(self):
        self.seed(published_count=2)
        original = Competition.objects.get(code='demo-r1-public-001')
        self.seed(published_count=4)
        self.assertEqual(Competition.objects.filter(publication_status='published').count(), 4)
        self.assertEqual(Competition.objects.get(pk=original.pk).published_at, original.published_at)
        self.assertEqual(get_user_model().objects.count(), 3)
        self.assertEqual(CompetitionTaxonomy.objects.count(), 6)

    def test_late_code_collision_rolls_back_entire_batch(self):
        Competition.objects.create(code='demo-r1-public-002', title='既有非样例记录', edition='2026')
        before = self.snapshot()
        with self.assertRaisesMessage(CommandError, '编码已被非样例记录占用'):
            self.seed(published_count=3)
        self.assertEqual(self.snapshot(), before)

    def test_existing_login_account_is_not_overwritten(self):
        user = get_user_model().objects.create_user('cxdemo-r1-001@tongji.edu.cn')
        before = self.snapshot()
        with self.assertRaisesMessage(CommandError, '非样例账号占用'):
            self.seed()
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(user.is_active)

    def test_invalid_count_is_rejected_without_writes(self):
        for count in (0, -1, 501):
            with self.subTest(count=count), self.assertRaises(CommandError):
                self.seed(published_count=count)
        self.assertFalse(get_user_model().objects.exists())

    @override_settings(DEBUG=False)
    def test_non_development_configuration_is_rejected(self):
        with self.assertRaisesMessage(CommandError, '仅限本地开发环境'):
            self.seed()
        self.assertFalse(get_user_model().objects.exists())
