"""仅 PostgreSQL 验证真实事务并发，SQLite 不冒充行锁验证。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, close_old_connections
from django.test import TransactionTestCase, override_settings
from .models import Application, Membership
from . import services as s
from .errors import BusinessError
from . import test_services as fixtures


@skipUnless(connection.vendor == 'postgresql', '需要 PostgreSQL 行锁及事务 advisory lock')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TeamConcurrencyTests(TransactionTestCase):
    user = fixtures.TeamFlowTests.user
    card_data = fixtures.TeamFlowTests.card_data
    card = fixtures.TeamFlowTests.card
    apply = fixtures.TeamFlowTests.apply
    action = fixtures.TeamFlowTests.action

    def setUp(self):
        self.previous_timeout = connection.settings_dict['OPTIONS'].get('connect_timeout', 5)
        # 并行测试建连接可能受本机安全扫描影响；仅延长握手，不延长事务锁等待。
        connection.settings_dict['OPTIONS']['connect_timeout'] = 15
        fixtures.TeamFlowTests.setUp(self)

    def tearDown(self):
        connection.settings_dict['OPTIONS']['connect_timeout'] = self.previous_timeout
        super().tearDown()

    def confirm_in_parallel(self, pairs):
        barrier = Barrier(len(pairs))
        def worker(pair):
            close_old_connections()
            try:
                app_id, actor_id = pair
                actor = get_user_model().objects.get(pk=actor_id)
                barrier.wait(timeout=20)
                try:
                    app = s.application_action(app_id, actor=actor, action='confirm',
                        data={'expected_version': 1, 'expected_application_version': 1})
                    return app.status
                except BusinessError as exc:
                    return str(exc.detail['code'])
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=len(pairs)) as pool:
            results = list(pool.map(worker, pairs))
        return results

    def test_two_applicants_compete_for_last_slot(self):
        card = self.card(recruitment_quota=1)
        first, second = self.apply(card), self.apply(card, self.third)
        for app in (first, second):
            self.action(app, 'accept')
            self.action(app, 'confirm', app.applicant)
        results = self.confirm_in_parallel([(first.pk, self.owner.pk), (second.pk, self.owner.pk)])
        self.assertEqual(results.count('joined'), 1)
        self.assertEqual(Membership.objects.filter(application__recruitment=card, ended_at=None).count(), 1)
        self.assertEqual(Application.objects.filter(recruitment=card, status='ended', end_reason='full').count(), 1)

    def test_same_applicant_cannot_join_two_teams_in_one_edition(self):
        first_card, second_card = self.card(), self.card(actor=self.third)
        first, second = self.apply(first_card), self.apply(second_card)
        self.action(first, 'accept')
        self.action(second, 'accept', self.third)
        self.action(first, 'confirm')
        self.action(second, 'confirm', self.third)
        results = self.confirm_in_parallel([(first.pk, self.student.pk), (second.pk, self.student.pk)])
        self.assertEqual(results.count('joined'), 1)
        self.assertEqual(Membership.objects.filter(user=self.student, competition=self.competition, ended_at=None).count(), 1)
        self.assertEqual(Application.objects.filter(applicant=self.student, status='ended', end_reason='joined_other_team').count(), 1)

    def test_quota_edit_and_last_confirmation_never_overfill(self):
        card = self.card(recruitment_quota=1)
        app = self.apply(card)
        self.action(app, 'accept')
        self.action(app, 'confirm', self.student)
        barrier = Barrier(2)
        def worker(kind):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.owner.pk)
                barrier.wait(timeout=20)
                try:
                    if kind == 'edit':
                        s.edit_recruitment(card.pk, actor=actor, data={'expected_version': 1, 'recruitment_quota': 0})
                    else:
                        s.application_action(app.pk, actor=actor, action='confirm',
                                             data={'expected_version': 1, 'expected_application_version': 1})
                    return 'success'
                except (BusinessError, ValidationError):
                    return 'rejected'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, ['edit', 'confirm']))
        card.refresh_from_db()
        self.assertEqual(results.count('success'), 1)
        self.assertLessEqual(card.joined_member_count, card.current_revision.recruitment_quota)
