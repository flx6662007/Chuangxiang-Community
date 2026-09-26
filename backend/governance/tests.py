"""独立验证治理权限与状态，不向外发信或修改运行数据。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import UserRestriction
from competitions.models import Competition, CompetitionSource, CompetitionTaxonomy
from teams import services as team_services
from teams.errors import BusinessError
from teams.models import RecruitmentOption
from .models import AdminAction, Appeal, Report
from . import services as s

BASE = '/api/v1/governance/'
PASSWORD = 'OnlyTesting!River47'


def make_competition(code='gov-test-2026', published=True):
    category, _ = CompetitionTaxonomy.objects.get_or_create(code='gov-test', defaults={'kind': 'category', 'name': '治理测试'})
    now = timezone.now()
    obj = s.save(Competition(code=code, title='治理隔离测试赛事', edition='2026', category=category,
        summary='测试', description='隔离测试', participation_type='team', recruitment_note='测试招募期限',
        recruitment_deadline=now + timedelta(days=20)))
    s.save(CompetitionSource(competition=obj, source_type='official', source_name='测试来源',
        source_url='https://example.org/test', is_primary=True, last_verified_at=now))
    if not published:
        return obj
    obj.publication_status = 'published'
    obj.recruitment_enabled = True
    obj.published_at = obj.last_verified_at = now
    return s.save(obj)


def make_user(name, staff=False):
    user = get_user_model().objects.create_user(name + '@tongji.edu.cn', PASSWORD, is_staff=staff)
    if staff:
        user.user_permissions.add(*Permission.objects.filter(codename__in=['change_report', 'view_report', 'change_appeal', 'view_appeal', 'change_recruitment']))
    return user


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GovernanceTests(TestCase):
    def setUp(self):
        self.student = make_user('gov-student')
        self.other = make_user('gov-other')
        self.admin = make_user('gov-admin', True)
        self.reviewer = make_user('gov-reviewer', True)
        self.competition = make_competition()
        self.client = APIClient()
        self.client.force_authenticate(self.student)

    def report_data(self, **extra):
        return {'target_type': 'competition', 'target_id': self.competition.pk,
            'reason': 'false_information', 'description': '请核对来源中的报名日期。', **extra}

    def restriction(self, user=None, **extra):
        now = timezone.now()
        return s.save(UserRestriction(user=user or self.student, created_by=self.admin, reason='隔离测试限制',
            starts_at=now, expires_at=now + timedelta(hours=24), **extra))

    def appeal_data(self, restriction=None, **extra):
        restriction = restriction or self.restriction()
        return {'target_type': 'restriction', 'target_id': restriction.pk, 'description': '请由另一名管理员复核依据。', **extra}

    def review(self, row, outcome=None, actor=None):
        return s.review_record(type(row), row.pk, actor=actor or self.admin,
            outcome=outcome or ('confirmed' if isinstance(row, Report) else 'upheld'), feedback='已核对原文并记录复核依据。')

    def card(self):
        self.student.wechat_id = 'gov_test'
        self.student.save()
        EmailAddress.objects.create(user=self.student, email=self.student.email, primary=True, verified=True)
        s.save(RecruitmentOption(code='gov-developer', kind='role', name='测试开发角色'))
        return team_services.publish_recruitment(actor=self.student, data={
            'competition_id': self.competition.pk, 'duration_days': 7, 'existing_member_count': 1, 'recruitment_quota': 2,
            'foundation_requirement': 'beginner_ok', 'weekly_effort': 'over_2_to_5', 'collaboration_mode': 'online',
            'collaboration_goal': '', 'expected_duration': '', 'current_skills': [], 'required_roles': ['gov-developer'],
            'required_skills': [], 'campuses': [],
        })

    def test_all_endpoints_require_login(self):
        self.client.force_authenticate(None)
        for path in ('options/', 'reports/', 'reports/1/', 'appeals/', 'appeals/1/', 'appeal-targets/'):
            self.assertEqual(self.client.get(BASE + path).status_code, 403, path)
        self.assertEqual(self.client.post(BASE + 'reports/', self.report_data(), format='json').status_code, 403)

    def test_unverified_restricted_account_can_report_without_automatic_punishment(self):
        restriction = self.restriction()
        self.assertFalse(EmailAddress.objects.filter(user=self.student, verified=True).exists())
        response = self.client.post(BASE + 'reports/', self.report_data(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['status'], 'pending')
        self.competition.refresh_from_db()
        restriction.refresh_from_db()
        self.assertEqual(self.competition.publication_status, 'published')
        self.assertEqual(UserRestriction.objects.count(), 1)
        self.assertIsNone(restriction.revoked_at)
        self.assertEqual(AdminAction.objects.count(), 0)

    def test_own_records_only_and_read_only_history(self):
        own = s.submit_report(actor=self.student, data=self.report_data())
        other = s.submit_report(actor=self.other, data=self.report_data())
        response = self.client.get(BASE + 'reports/')
        self.assertEqual([row['id'] for row in response.data['results']], [own.pk])
        self.assertEqual(self.client.get(BASE + f'reports/{other.pk}/').status_code, 404)
        self.assertEqual(self.client.patch(BASE + f'reports/{own.pk}/', {'description': '改写'}).status_code, 405)
        self.assertEqual(self.client.delete(BASE + f'reports/{own.pk}/').status_code, 405)
        own.description = '篡改说明'
        with self.assertRaises(ValidationError):
            own.full_clean()
        self.assertFalse({'submitted_by', 'reviewed_by', 'email', 'wechat_id', 'phone_number'} & set(response.data['results'][0]))

    def test_input_whitelist_enums_limits_and_options(self):
        for extra in ({'reason': 'arbitrary'}, {'description': '   '}, {'description': '字' * 1001},
                      {'target_type': 'user'}, {'submitted_by': self.other.pk}, {'status': 'confirmed'}):
            response = self.client.post(BASE + 'reports/', self.report_data(**extra), format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Report.objects.count(), 0)
        self.assertEqual(len(self.client.get(BASE + 'options/').data['report_reasons']), 4)
        self.assertEqual(self.client.get(BASE + 'reports/?status=anything').status_code, 400)

    def test_private_draft_and_hidden_demo_targets_cannot_be_probed(self):
        self.competition = make_competition('gov-draft-2026', published=False)
        response = self.client.post(BASE + 'reports/', self.report_data(), format='json')
        self.assertEqual(response.status_code, 404, response.data)
        self.competition = make_competition('demo-r1-governance')
        self.competition.title = '【虚构样例】治理测试'
        s.save(self.competition)
        self.assertEqual(self.client.post(BASE + 'reports/', self.report_data(), format='json').status_code, 404)
        self.assertEqual(Report.objects.count(), 0)

    def test_withdrawn_recruitment_is_reportable_only_to_related_user(self):
        card = self.card()
        team_services.withdraw_recruitment(card.pk, actor=self.admin, reason='测试下架')
        data = self.report_data(target_type='recruitment', target_id=card.pk)
        self.assertEqual(self.client.post(BASE + 'reports/', data, format='json').status_code, 201)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(BASE + 'reports/', data, format='json').status_code, 404)

    def test_pending_duplicate_is_rejected_but_reviewed_result_can_receive_new_evidence(self):
        row = s.submit_report(actor=self.student, data=self.report_data())
        response = self.client.post(BASE + 'reports/', self.report_data(reason='other'), format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'duplicate_pending')
        self.review(row)
        self.assertEqual(self.client.post(BASE + 'reports/', self.report_data(), format='json').status_code, 201)

    def test_report_minute_and_daily_limits(self):
        now = timezone.now()
        for index in range(10):
            # 不同时刻保留不可变历史，避免用更新历史来模拟限流窗口。
            at = now + timedelta(minutes=2 * index)
            with patch('governance.services.timezone.now', return_value=at):
                row = s.submit_report(actor=self.student, data=self.report_data())
                self.review(row)
        with patch('governance.services.timezone.now', return_value=now + timedelta(minutes=25)):
            response = self.client.post(BASE + 'reports/', self.report_data(), format='json')
            self.assertEqual(response.status_code, 429, response.data)
        for _ in range(3):
            row = s.submit_report(actor=self.other, data=self.report_data())
            self.review(row)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(BASE + 'reports/', self.report_data(), format='json').status_code, 429)

    def test_report_review_needs_permission_and_cannot_be_overwritten(self):
        row = s.submit_report(actor=self.student, data=self.report_data())
        for actor in (self.student, make_user('gov-no-permission', True)):
            if actor != self.student:
                actor.user_permissions.clear()
            with self.assertRaises(BusinessError):
                self.review(row, actor=actor)
        self.review(row, 'dismissed')
        response = self.client.get(BASE + f'reports/{row.pk}/')
        self.assertEqual(response.data['status'], 'dismissed')
        self.assertEqual(response.data['allowed_actions'], ['appeal'])
        self.assertTrue(response.data['feedback'])
        with self.assertRaises(BusinessError):
            self.review(row, 'confirmed')
        row.refresh_from_db()
        row.feedback = '替换旧结论'
        with self.assertRaises(ValidationError):
            row.full_clean()

    def test_admin_cannot_review_own_report(self):
        row = s.submit_report(actor=self.admin, data=self.report_data())
        with self.assertRaises(BusinessError):
            self.review(row)
        self.review(row, actor=self.reviewer)

    def test_own_restriction_appeal_and_independent_review_without_auto_reversal(self):
        restriction = self.restriction()
        response = self.client.post(BASE + 'appeals/', self.appeal_data(restriction), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        appeal = Appeal.objects.get(pk=response.data['id'])
        with self.assertRaises(BusinessError) as caught:
            self.review(appeal, actor=self.admin)
        self.assertEqual(caught.exception.status_code, 403)
        self.review(appeal, actor=self.reviewer)
        restriction.refresh_from_db()
        self.assertIsNone(restriction.revoked_at)
        self.assertTrue(restriction.is_effective)
        self.assertEqual(AdminAction.objects.count(), 0)
        result = self.client.get(BASE + f'appeals/{appeal.pk}/').data
        self.assertEqual(result['status'], 'upheld')
        self.assertIn('不自动', result['effect_note'])

    def test_other_users_appeal_targets_and_pending_report_are_inaccessible(self):
        restricted_other = self.restriction(self.other)
        response = self.client.post(BASE + 'appeals/', self.appeal_data(restricted_other), format='json')
        self.assertEqual(response.status_code, 404)
        report = s.submit_report(actor=self.student, data=self.report_data())
        data = {'target_type': 'report', 'target_id': report.pk, 'description': '提前申诉'}
        self.assertEqual(self.client.post(BASE + 'appeals/', data, format='json').status_code, 404)
        self.review(report, 'dismissed')
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(BASE + 'appeals/', data, format='json').status_code, 404)

    def test_recruitment_action_appeal_is_only_for_its_recruiter(self):
        card = self.card()
        team_services.withdraw_recruitment(card.pk, actor=self.admin, reason='需核实信息')
        action = AdminAction.objects.get(recruitment=card, action='withdraw')
        data = {'target_type': 'recruitment_action', 'target_id': action.pk, 'description': '请复核下架原因'}
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(BASE + 'appeals/', data, format='json').status_code, 404)
        self.client.force_authenticate(self.student)
        response = self.client.post(BASE + 'appeals/', data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        appeal = Appeal.objects.get(pk=response.data['id'])
        with self.assertRaises(BusinessError):
            self.review(appeal)
        self.review(appeal, actor=self.reviewer)
        card.refresh_from_db()
        self.assertEqual(card.publication_status, 'withdrawn')
        self.assertEqual(AdminAction.objects.filter(recruitment=card).count(), 1)

    def test_appeal_against_report_result_uses_original_reviewer_and_preserves_result(self):
        row = s.submit_report(actor=self.student, data=self.report_data())
        self.review(row, 'dismissed')
        data = {'target_type': 'report', 'target_id': row.pk, 'description': '有新的原文依据，请独立复核'}
        response = self.client.post(BASE + 'appeals/', data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.get(BASE + f'reports/{row.pk}/').data['allowed_actions'], [])
        appeal = Appeal.objects.get(pk=response.data['id'])
        with self.assertRaises(BusinessError):
            self.review(appeal)
        self.review(appeal, actor=self.reviewer)
        row.refresh_from_db()
        self.assertEqual(row.status, 'dismissed')

    def test_appeal_targets_pagination_duplicates_and_privacy(self):
        own = self.restriction()
        self.restriction(self.other)
        report = s.submit_report(actor=self.student, data=self.report_data())
        self.review(report)
        response = self.client.post(BASE + 'appeals/', self.appeal_data(own), format='json')
        own_appeal_id = response.data['id']
        self.assertEqual(self.client.post(BASE + 'appeals/', self.appeal_data(own), format='json').status_code, 409)
        response = self.client.get(BASE + 'appeal-targets/')
        self.assertEqual(response.data['count'], 2)
        restricted = next(row for row in response.data['results'] if row['target_type'] == 'restriction')
        self.assertFalse(restricted['can_appeal'])
        self.assertEqual(restricted['pending_appeal_id'], own_appeal_id)
        self.assertEqual(len(self.client.get(BASE + 'appeal-targets/?page_size=1').data['results']), 1)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(BASE + f'appeals/{own_appeal_id}/').status_code, 404)
        self.assertEqual(self.client.get(BASE + 'appeals/').data['count'], 0)

    def test_appeal_rate_limit_and_nonwithdraw_action_rejected(self):
        for _ in range(2):
            restriction = self.restriction()
            s.submit_appeal(actor=self.student, data=self.appeal_data(restriction))
        response = self.client.post(BASE + 'appeals/', self.appeal_data(), format='json')
        self.assertEqual(response.status_code, 429)
        action = s.save(AdminAction(action='edit', competition=self.competition, actor=self.admin, changes={'fields': ['summary']}))
        self.client.force_authenticate(self.other)
        data = {'target_type': 'recruitment_action', 'target_id': action.pk, 'description': '不应允许'}
        self.assertEqual(self.client.post(BASE + 'appeals/', data, format='json').status_code, 404)

    def test_database_pending_uniqueness_and_complete_review_constraints(self):
        row = s.submit_report(actor=self.student, data=self.report_data())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Report.objects.create(submitted_by=self.student, competition=self.competition, target_title='测试',
                description='重复', reason='other')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Report.objects.filter(pk=row.pk).update(status='confirmed')
        appeal = s.submit_appeal(actor=self.student, data=self.appeal_data())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Appeal.objects.create(submitted_by=self.student, restriction=appeal.restriction,
                target_title='测试', description='重复')

    def test_csrf_protection_applies_to_authenticated_reports(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.student, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(client.post(BASE + 'reports/', self.report_data(), content_type='application/json').status_code, 403)
        client.get('/api/v1/accounts/csrf/')
        response = client.post(BASE + 'reports/', self.report_data(), content_type='application/json',
            HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 201, response.content)

    def test_admin_form_checks_review_permission_and_saves_feedback(self):
        report = s.submit_report(actor=self.student, data=self.report_data())
        self.client.force_authenticate(None)
        self.client.force_login(self.admin, backend='django.contrib.auth.backends.ModelBackend')
        url = f'/admin/governance/report/{report.pk}/review/'
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {'outcome': 'confirmed', 'feedback': '已核对，后续处理另行记录。'})
        self.assertEqual(response.status_code, 302, response.content)
        report.refresh_from_db()
        self.assertEqual(report.status, 'confirmed')
        self.assertEqual(self.client.get('/admin/governance/report/add/').status_code, 403)
        appeal = s.submit_appeal(actor=self.student, data=self.appeal_data())
        response = self.client.post(f'/admin/governance/appeal/{appeal.pk}/review/', {'outcome': 'upheld', 'feedback': '自己复核'})
        self.assertEqual(response.status_code, 200)
        appeal.refresh_from_db()
        self.assertEqual(appeal.status, 'pending')

    def test_generic_admin_save_cannot_overwrite_pending_or_completed_review(self):
        report = s.submit_report(actor=self.student, data=self.report_data())
        appeal = s.submit_appeal(actor=self.student, data=self.appeal_data())
        self.client.force_authenticate(None)
        self.client.force_login(self.reviewer, backend='django.contrib.auth.backends.ModelBackend')
        for row, outcome in ((report, 'confirmed'), (appeal, 'upheld')):
            with self.subTest(model=type(row).__name__):
                model = type(row)
                base = f'/admin/governance/{model._meta.model_name}/{row.pk}/'
                stale = model.objects.get(pk=row.pk)
                initial = model.objects.filter(pk=row.pk).values().get()
                response = self.client.get(base + 'change/')
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'name="_save"')
                response = self.client.post(base + 'change/', {'_save': '保存'})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(model.objects.filter(pk=row.pk).values().get(), initial)
                # 专用表单依旧可以通过带锁服务完成独立复核。
                response = self.client.post(base + 'review/', {'outcome': outcome, 'feedback': '复核后的正式反馈'})
                self.assertEqual(response.status_code, 302, response.content)
                reviewed = model.objects.filter(pk=row.pk).values().get()
                self.assertEqual(reviewed['status'], outcome)
                self.assertEqual(reviewed['feedback'], '复核后的正式反馈')
                # 迟到的通用详情 POST 与已读取 pending 的旧实例均不能回写。
                self.assertEqual(self.client.post(base + 'change/', {'status': 'pending', 'feedback': ''}).status_code, 403)
                with self.assertRaises(PermissionDenied):
                    admin.site._registry[model].save_model(None, stale, None, True)
                self.assertEqual(model.objects.filter(pk=row.pk).values().get(), reviewed)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GovernanceConcurrencyTests(TransactionTestCase):
    def test_concurrent_duplicate_submission_has_one_pending_record(self):
        if connection.vendor != 'postgresql':
            self.skipTest('行锁并发验收使用 PostgreSQL。')
        user = make_user('gov-racing')
        competition = make_competition()
        data = {'target_type': 'competition', 'target_id': competition.pk, 'reason': 'other', 'description': '并发测试'}
        def submit():
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=user.pk)
                try:
                    s.submit_report(actor=actor, data=data)
                    return 'created'
                except BusinessError as exc:
                    return str(exc.detail['code'])
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
        self.assertCountEqual(results, ['created', 'duplicate_pending'])
        self.assertEqual(Report.objects.count(), 1)
