"""补充绕过模型校验的写入测试，以及实际迁移与 PostgreSQL 索引检查。"""

from datetime import date
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase
from django.utils import timezone

from .models import Competition, CompetitionSource, CompetitionTaxonomy


class DatabaseConstraintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('database-test@tongji.edu.cn')
        cls.category = CompetitionTaxonomy.objects.create(code='db-category', kind='category', name='数据库测试分类')
        cls.tag = CompetitionTaxonomy.objects.create(code='db-tag', kind='tag', name='数据库测试标签')
        cls.competition = Competition.objects.create(code='db-competition', title='数据库测试赛事', edition='测试届次')
        cls.source = CompetitionSource.objects.create(
            competition=cls.competition, source_type='official', source_name='虚构来源',
            source_url='https://example.org/database-test', is_primary=True,
        )

    def assert_rejected(self, instance, changes):
        # 故意绕过 full_clean，确认拒绝写入的是数据库约束。
        with self.assertRaises(IntegrityError), transaction.atomic():
            type(instance).objects.filter(pk=instance.pk).update(**changes)

    def test_user_not_null_and_public_code_constraints(self):
        for changes in ({'email': None}, {'wechat_id': None}, {'phone_number': None}, {'public_code': 'invalid'}):
            with self.subTest(changes=changes):
                self.assert_rejected(self.user, changes)
        other = get_user_model().objects.create_user('other-database-test@tongji.edu.cn')
        self.assert_rejected(other, {'public_code': self.user.public_code})

    def test_competition_code_unique_and_required_columns(self):
        other = Competition.objects.create(code='db-other', title='另一个虚构赛事', edition='测试届次')
        for changes in ({'code': self.competition.code}, {'title': None}, {'edition': None}, {'participation_type': 'invalid'}):
            with self.subTest(changes=changes):
                self.assert_rejected(other, changes)

    def test_publication_and_recruitment_database_guards(self):
        now = timezone.now()
        for changes in (
            {'published_at': now},
            {'publication_status': 'published'},
            {'publication_status': 'published', 'published_at': now},
            {'publication_status': 'withdrawn', 'published_at': now, 'withdrawal_reason': '  '},
            {'recruitment_enabled': True},
            {'team_size_max': 0},
        ):
            with self.subTest(changes=changes):
                self.assert_rejected(self.competition, changes)

    def test_all_three_deadline_groups_reject_missing_pairs(self):
        for prefix in ('registration_deadline', 'submission_deadline', 'campus_deadline'):
            for changes in (
                {prefix + '_timezone': 'Asia/Shanghai'},
                {prefix + '_at': timezone.now()},
                {prefix: date(2026, 10, 1), prefix + '_at': timezone.now()},
            ):
                with self.subTest(changes=changes):
                    self.assert_rejected(self.competition, changes)

    def test_taxonomy_and_source_database_guards(self):
        for changes in ({'code': 'INVALID'}, {'name': ' \t '}, {'kind': 'invalid'}, {'sort_order': -1}):
            with self.subTest(changes=changes):
                self.assert_rejected(self.category, changes)
        for changes in ({'source_url': 'ftp://example.org/file'}, {'source_name': '  '}, {'source_type': 'invalid'}):
            with self.subTest(changes=changes):
                self.assert_rejected(self.source, changes)
        self.assert_rejected(self.tag, {'kind': 'category', 'name': self.category.name})
        self.assert_rejected(self.tag, {'code': self.category.code})

    def test_tag_relation_unique_pair(self):
        self.competition.tags.add(self.tag)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Competition.tags.through.objects.create(competition=self.competition, competitiontaxonomy=self.tag)

    def test_missing_foreign_keys_rejected_even_when_deferred(self):
        for instance, changes in (
            (self.competition, {'category_id': 999999999}),
            (self.competition, {'created_by_id': 999999999}),
            (self.source, {'competition_id': 999999999}),
        ):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                type(instance).objects.filter(pk=instance.pk).update(**changes)
                connection.check_constraints()

    def test_initial_migrations_are_applied_and_default_user_table_is_absent(self):
        applied = MigrationRecorder(connection).applied_migrations()
        self.assertIn(('accounts', '0001_initial'), applied)
        self.assertIn(('competitions', '0001_initial'), applied)
        self.assertIn('accounts_user', connection.introspection.table_names())
        self.assertNotIn('auth_user', connection.introspection.table_names())

    @skipUnless(connection.vendor == 'postgresql', 'PostgreSQL catalog verification')
    def test_postgresql_named_constraints_indexes_and_column_types(self):
        with connection.cursor() as cursor:
            for model in (get_user_model(), Competition, CompetitionSource, CompetitionTaxonomy):
                actual = connection.introspection.get_constraints(cursor, model._meta.db_table)
                for constraint in model._meta.constraints:
                    self.assertIn(constraint.name, actual)
                for index in model._meta.indexes:
                    self.assertTrue(actual[index.name]['index'])
            cursor.execute("SELECT indexdef FROM pg_indexes WHERE schemaname = current_schema() AND indexname = 'comp_one_primary_source'")
            primary_index = cursor.fetchone()[0]
            self.assertIn('UNIQUE INDEX', primary_index)
            self.assertIn('WHERE is_primary', primary_index)
            cursor.execute("SELECT indexdef FROM pg_indexes WHERE schemaname = current_schema() AND indexname = 'user_email_ci_unique'")
            email_index = cursor.fetchone()[0]
            self.assertIn('UNIQUE INDEX', email_index)
            self.assertIn('lower(', email_index)
            cursor.execute(
                'SELECT column_name, data_type FROM information_schema.columns '
                'WHERE table_schema = current_schema() AND table_name = %s', [Competition._meta.db_table],
            )
            columns = dict(cursor.fetchall())
            self.assertEqual(columns['registration_deadline'], 'date')
            self.assertEqual(columns['registration_deadline_at'], 'timestamp with time zone')
