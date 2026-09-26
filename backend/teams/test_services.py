"""完整事务流程、授权与到期边界；不把模型存在当作业务完成。"""
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import include, path
from django.utils import timezone
from allauth.account.models import EmailAddress
from rest_framework.test import APIClient
from competitions.models import Competition, CompetitionTaxonomy, CompetitionSource
from notifications.models import Notification, BusinessEvent
from accounts.models import UserRestriction
from . import services as s
from .errors import BusinessError
from .models import Recruitment, RecruitmentOption, Application, Membership, Team, DepartureRequest, DissolutionRequest, RecruitmentRevision, RecruitmentBaselineMember, DissolutionResponse

urlpatterns = [path('api/v1/', include('teams.urls')), path('api/v1/notifications/', include('notifications.urls'))]


@override_settings(ROOT_URLCONF=__name__, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TeamFlowTests(TestCase):
    def setUp(self):
        self.owner = self.user('owner')
        self.student = self.user('student')
        self.third = self.user('third')
        self.category = CompetitionTaxonomy.objects.create(code='test-category', kind='category', name='测试')
        now = timezone.now()
        self.competition = s.save(Competition(code='test-2026', title='测试赛事', edition='2026', category=self.category,
            summary='测试', description='仅在隔离测试库使用', recruitment_note='测试招募期', recruitment_deadline=now + timedelta(days=30),
            recruitment_enabled=False, participation_type='team'))
        s.save(CompetitionSource(competition=self.competition, source_type='official', source_name='测试来源',
            source_url='https://example.org/test', is_primary=True, last_verified_at=now))
        self.competition.publication_status = 'published'
        self.competition.recruitment_enabled = True
        self.competition.published_at = self.competition.last_verified_at = now
        s.save(self.competition)
        self.role = s.save(RecruitmentOption(code='developer', kind='role', name='开发'))
        self.skill = s.save(RecruitmentOption(code='python', kind='skill', name='Python'))
        self.campus = s.save(RecruitmentOption(code='campus-a', kind='campus', name='测试校区'))
        self.client = APIClient()

    def user(self, name):
        user = get_user_model().objects.create_user(name + '@tongji.edu.cn', password='safe-test-password', wechat_id=name + '_test')
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        return user

    def card_data(self, **changes):
        data = dict(competition_id=self.competition.pk, duration_days=7, existing_member_count=1, recruitment_quota=2,
            foundation_requirement='beginner_ok', weekly_effort='over_2_to_5', collaboration_mode='online',
            collaboration_goal='', expected_duration='', current_skills=[], required_roles=['developer'], required_skills=[], campuses=[])
        data.update(changes)
        return data

    def card(self, actor=None, **changes):
        return s.publish_recruitment(actor=actor or self.owner, data=self.card_data(**changes))

    def apply(self, card, user=None):
        return s.submit_application(card.pk, actor=user or self.student, data={'expected_version': card.current_revision.version,
            'weekly_effort': 'over_2_to_5', 'desired_roles': ['developer'], 'skills': ['python']})

    def action(self, app, action, actor=None, **extra):
        app.refresh_from_db()
        data = {'expected_version': app.recruitment.current_revision.version,
                'expected_application_version': app.current_revision.version, **extra}
        return s.application_action(app.pk, actor=actor or self.owner, action=action, data=data)

    def join(self, card, user=None):
        user = user or self.student
        app = self.apply(card, user)
        self.action(app, 'accept')
        self.action(app, 'confirm', user)
        self.action(app, 'confirm')
        app.refresh_from_db()
        return app

    def assert_conflict(self, code, function, *args, **kwargs):
        with self.assertRaises(BusinessError) as raised:
            function(*args, **kwargs)
        self.assertEqual(str(raised.exception.detail['code']), code)

    def test_preview_checks_full_template_and_leaves_no_rows(self):
        result = s.preview_recruitment(actor=self.owner, data=self.card_data())
        self.assertGreater(result['expires_at'], timezone.now())
        self.assertEqual(Team.objects.count(), 0)
        self.assertEqual(Membership.objects.count(), 0)
        with self.assertRaises(ValidationError):
            s.preview_recruitment(actor=self.owner, data=self.card_data(collaboration_mode='offline'))
        self.assertEqual(Recruitment.objects.count(), 0)

    def test_publication_creates_complete_graph_and_unique_slot(self):
        card = self.card()
        self.assertEqual(card.current_revision.version, 1)
        self.assertEqual(RecruitmentBaselineMember.objects.filter(revision=card.current_revision).count(), 1)
        self.assertEqual(Membership.objects.filter(team=card.team, ended_at=None).count(), 1)
        self.assert_conflict('active_card_exists', self.card, team_id=card.team_id)
        self.assertEqual(Recruitment.objects.count(), 1)

    def test_effective_expiry_is_capped_and_edits_never_renew(self):
        self.competition.recruitment_deadline = timezone.now() + timedelta(days=2)
        s.save(self.competition)
        card = self.card()
        self.assertEqual(card.expires_at, self.competition.recruitment_deadline)
        edited = s.edit_recruitment(card.pk, actor=self.owner, data={'expected_version': 1, 'recruitment_quota': 3})
        self.assertEqual(edited.expires_at, card.expires_at)
        self.assertEqual(edited.current_revision.version, 2)
        self.assert_conflict('stale_version', s.edit_recruitment, card.pk, actor=self.owner, data={'expected_version': 1, 'recruitment_quota': 4})

    def test_same_save_does_not_make_versions_or_events(self):
        card = self.card()
        s.edit_recruitment(card.pk, actor=self.owner, data={'expected_version': 1, 'recruitment_quota': 2})
        self.assertEqual(RecruitmentRevision.objects.count(), 1)
        self.assertEqual(BusinessEvent.objects.count(), 0)

    def test_invalid_template_rolls_back_new_team(self):
        with self.assertRaises(ValidationError):
            self.card(collaboration_mode='offline', campuses=[])
        self.assertEqual(Team.objects.count(), 0)
        with self.assertRaises(ValidationError):
            self.card(required_roles=['python'])
        self.assertEqual(Membership.objects.count(), 0)

    def test_disabled_option_is_retained_only_in_same_relation(self):
        card = self.card()
        self.role.is_active = False
        s.save(self.role)
        edited = s.edit_recruitment(card.pk, actor=self.owner, data={'expected_version': 1, 'recruitment_quota': 3})
        self.assertEqual(edited.current_revision.required_roles.get().code, 'developer')
        with self.assertRaises(ValidationError):
            self.card(actor=self.third)
        with self.assertRaises(ValidationError):
            s.edit_recruitment(card.pk, actor=self.owner, data={'expected_version': 2, 'required_skills': ['developer']})

    def test_accept_and_first_confirmation_do_not_take_slot(self):
        card = self.card(recruitment_quota=1)
        app = self.apply(card)
        self.action(app, 'accept')
        self.action(app, 'confirm', self.student)
        self.assertEqual(card.joined_member_count, 0)
        self.action(app, 'confirm')
        self.assertEqual(card.joined_member_count, 1)
        count = BusinessEvent.objects.count()
        self.action(app, 'confirm')
        self.assertEqual(card.joined_member_count, 1)
        self.assertEqual(BusinessEvent.objects.count(), count)

    def test_full_ends_other_applications_and_remains_unique_card(self):
        card = self.card(recruitment_quota=1)
        other = self.apply(card, self.third)
        self.action(other, 'accept')
        self.join(card)
        other.refresh_from_db()
        self.assertEqual(other.end_reason, 'full')
        self.assertFalse(other.can_view_contact(self.third.pk))
        self.assert_conflict('active_card_exists', self.card, team_id=card.team_id)

    def test_single_edition_membership_and_other_apps_ended(self):
        card = self.card()
        other_card = self.card(actor=self.third)
        other_app = self.apply(other_card)
        self.join(card)
        other_app.refresh_from_db()
        self.assertEqual(other_app.end_reason, 'joined_other_team')
        self.assert_conflict('already_member', self.card, actor=self.student)

    def test_edit_pauses_resets_confirmations_and_preserves_contact(self):
        card = self.card()
        app = self.apply(card)
        self.action(app, 'accept')
        self.action(app, 'confirm', self.student)
        s.edit_recruitment(card.pk, actor=self.owner, data={'expected_version': 1, 'weekly_effort': 'over_10'})
        app.refresh_from_db()
        self.assertTrue(app.is_paused)
        self.assertIsNone(app.applicant_confirmed_at)
        self.assertTrue(app.can_view_contact(self.student.pk))
        self.assert_conflict('application_paused', self.action, app, 'confirm')
        self.action(app, 'continue', self.student, weekly_effort='over_10', desired_roles=[], skills=[])
        app.refresh_from_db()
        self.assertEqual(app.current_revision.version, 2)
        self.assertFalse(app.is_paused)
        self.action(app, 'confirm')
        self.assertEqual(Membership.objects.filter(application=app).count(), 0)
        self.action(app, 'confirm', self.student)
        self.assertEqual(Membership.objects.filter(application=app).count(), 1)

    def test_withdraw_reject_end_revoke_and_no_reapplication(self):
        card = self.card()
        app = self.apply(card)
        self.action(app, 'withdraw', self.student)
        self.assert_conflict('already_applied', self.apply, card)
        other = self.apply(card, self.third)
        self.action(other, 'reject')
        self.assert_conflict('already_applied', self.apply, card, self.third)
        fourth = self.user('fourth')
        active = self.apply(card, fourth)
        self.action(active, 'accept')
        self.action(active, 'confirm', fourth)
        self.action(active, 'revoke-confirmation', fourth)
        active.refresh_from_db()
        self.assertIsNone(active.applicant_confirmed_at)
        self.action(active, 'end')
        active.refresh_from_db()
        self.assertFalse(active.can_view_contact(fourth.pk))

    def test_unauthorized_actions_and_unverified_new_actions(self):
        card = self.card()
        app = self.apply(card)
        self.assert_conflict('forbidden', self.action, app, 'accept', self.student)
        self.assert_conflict('forbidden', self.action, app, 'confirm', self.third)
        EmailAddress.objects.filter(user=self.third).update(verified=False)
        self.assert_conflict('account_ineligible', self.apply, card, self.third)

    def test_member_exit_reject_retains_relation_then_can_reapply(self):
        card = self.card()
        app = self.join(card)
        member = Membership.objects.get(application=app)
        req = s.request_departure(member.pk, actor=self.student, kind='exit')
        self.assertEqual(req.deadline_at - req.created_at, timedelta(hours=24))
        s.departure_action(req.pk, actor=self.owner, action='respond', response='reject')
        member.refresh_from_db()
        self.assertIsNone(member.ended_at)
        req2 = s.request_departure(member.pk, actor=self.owner, kind='removal')
        self.assertNotEqual(req.pk, req2.pk)
        s.departure_action(req2.pk, actor=self.student, action='respond', response='agree')
        member.refresh_from_db()
        self.assertEqual(member.end_reason, 'removal')
        self.assertEqual(card.remaining_slots, 2)
        self.assertFalse(app.can_view_contact(self.student.pk))

    def test_departure_timeout_cannot_be_overwritten_by_late_rejection(self):
        card = self.card()
        member = Membership.objects.get(application=self.join(card))
        req = s.request_departure(member.pk, actor=self.student, kind='exit')
        with patch('teams.services.timezone.now', return_value=req.deadline_at):
            result = s.departure_action(req.pk, actor=self.owner, action='respond', response='reject')
        self.assertEqual(result.status, 'timed_out')
        self.assertEqual(result.response, '')
        member.refresh_from_db()
        self.assertIsNotNone(member.ended_at)

    def test_departure_withdraw_and_same_request_idempotency(self):
        card = self.card()
        member = Membership.objects.get(application=self.join(card))
        req = s.request_departure(member.pk, actor=self.student, kind='exit')
        self.assertEqual(s.request_departure(member.pk, actor=self.student, kind='exit').pk, req.pk)
        self.assert_conflict('request_pending', s.request_departure, member.pk, actor=self.owner, kind='removal')
        s.departure_action(req.pk, actor=self.student, action='withdraw')
        member.refresh_from_db()
        self.assertIsNone(member.ended_at)

    def test_dissolution_reject_withdraw_and_all_agree(self):
        card = self.card()
        self.join(card)
        req = s.request_dissolution(card.team_id, actor=self.owner)
        self.assert_conflict('team_paused', s.edit_recruitment, card.pk, actor=self.owner, data={'expected_version': 1, 'recruitment_quota': 4})
        self.assert_conflict('card_unavailable', self.apply, card, self.third)
        s.dissolution_action(req.pk, actor=self.student, action='respond', response='reject')
        card.team.refresh_from_db()
        self.assertIsNone(card.team.dissolved_at)
        req2 = s.request_dissolution(card.team_id, actor=self.owner)
        s.dissolution_action(req2.pk, actor=self.owner, action='withdraw')
        req3 = s.request_dissolution(card.team_id, actor=self.owner)
        s.dissolution_action(req3.pk, actor=self.student, action='respond', response='agree')
        self.assertEqual(Membership.objects.filter(team=card.team, ended_at=None).count(), 0)
        card.refresh_from_db()
        self.assertEqual(card.close_reason, 'team_dissolved')

    def test_dissolution_timeout_preserves_no_fake_votes_and_ends_departure(self):
        card = self.card()
        member = Membership.objects.get(application=self.join(card))
        req = s.request_dissolution(card.team_id, actor=self.owner)
        departure = s.request_departure(member.pk, actor=self.student, kind='exit')
        with patch('teams.services.timezone.now', return_value=req.deadline_at):
            s.execute(self.competition.pk, None, lambda now: None)
        req.refresh_from_db()
        departure.refresh_from_db()
        self.assertEqual(req.completion_reason, 'timeout')
        self.assertEqual(departure.status, 'team_dissolved')
        self.assertEqual(DissolutionResponse.objects.get(request=req).response, '')

    def test_solo_dissolution_and_exit_during_dissolution(self):
        solo = self.card()
        req = s.request_dissolution(solo.team_id, actor=self.owner)
        self.assertEqual(req.completion_reason, 'no_other_members')
        self.client.force_authenticate(self.owner)
        history = self.client.get(f'/api/v1/teams/{solo.team_id}/').json()
        self.assertTrue(history['history_only'])
        self.assertEqual([item['id'] for item in history['dissolution_requests']], [req.pk])
        self.assertEqual(history['dissolution_requests'][0]['status'], 'completed')
        self.assertEqual(history['dissolution_requests'][0]['responses'], [])
        card = self.card()
        member = Membership.objects.get(application=self.join(card))
        req = s.request_dissolution(card.team_id, actor=self.owner)
        leave = s.request_departure(member.pk, actor=self.student, kind='exit')
        s.departure_action(leave.pk, actor=self.owner, action='respond', response='agree')
        req.refresh_from_db()
        self.assertEqual(req.status, 'completed')

    def test_expiry_settlement_persists_even_when_new_action_rejected(self):
        card = self.card(duration_days=3)
        app = self.apply(card)
        with patch('teams.services.timezone.now', return_value=card.expires_at):
            self.assert_conflict('card_unavailable', self.apply, card, self.third)
        card.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual(card.close_reason, 'expired')
        self.assertEqual(app.end_reason, 'expired')

    def test_new_round_baseline_counts_prior_members_and_departure(self):
        card = self.card()
        app = self.join(card)
        s.close_recruitment(card.pk, actor=self.owner, data={'expected_version': 1})
        new_card = self.card(team_id=card.team_id, existing_member_count=2, recruitment_quota=1)
        member = Membership.objects.get(application=app)
        leave = s.request_departure(member.pk, actor=self.student, kind='exit')
        s.departure_action(leave.pk, actor=self.owner, action='respond', response='agree')
        self.assertEqual(new_card.current_existing_member_count, 1)
        self.assertEqual(new_card.remaining_slots, 1)
        edited = s.edit_recruitment(new_card.pk, actor=self.owner, data={'expected_version': 1, 'weekly_effort': 'over_10'})
        self.assertEqual(edited.current_existing_member_count, 1)
        self.assertEqual(edited.current_revision.existing_member_count, 1)

    def test_competition_stop_ends_pending_preserves_joined_contact(self):
        card = self.card()
        joined = self.join(card)
        pending = self.apply(card, self.third)
        self.action(pending, 'accept')
        with s.lock_competition_graph(self.competition.pk):
            self.competition.recruitment_enabled = False
            s.save(self.competition)
            s.reconcile_competition(self.competition.pk)
        pending.refresh_from_db()
        joined.refresh_from_db()
        self.assertEqual(pending.end_reason, 'competition_stopped')
        self.assertFalse(pending.can_view_contact(self.third.pk))
        self.assertTrue(joined.can_view_contact(self.student.pk))

    def test_api_public_has_no_contacts_private_permissions_and_unknown_fields(self):
        card = self.card()
        public = self.client.get('/api/v1/recruitments/').json()
        text = str(public)
        for secret in ['wechat_id', 'phone_number', self.owner.email, self.owner.wechat_id]:
            self.assertNotIn(secret, text)
        self.client.force_authenticate(self.student)
        invalid = self.client.post('/api/v1/recruitments/', {**self.card_data(), 'title': '任意广告'}, format='json')
        self.assertEqual(invalid.status_code, 400)
        app = self.apply(card)
        self.assertEqual(self.client.get(f'/api/v1/applications/{app.pk}/contact/').status_code, 403)
        self.action(app, 'accept')
        contact = self.client.get(f'/api/v1/applications/{app.pk}/contact/')
        self.assertEqual(contact.status_code, 200)
        self.assertEqual(contact['Cache-Control'], 'no-store, private')
        self.assertEqual(contact.json()['wechat_id'], self.owner.wechat_id)
        self.client.force_authenticate(self.third)
        self.assertEqual(self.client.get(f'/api/v1/applications/{app.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/v1/teams/{card.team_id}/').status_code, 404)

    def test_api_actions_notifications_and_read_is_not_acceptance(self):
        card = self.card()
        self.client.force_authenticate(self.student)
        result = self.client.post(f'/api/v1/recruitments/{card.pk}/applications/', {'expected_version': 1,
            'weekly_effort': 'over_2_to_5', 'desired_roles': [], 'skills': []}, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        app = Application.objects.get(pk=result.json()['id'])
        s.edit_recruitment(card.pk, actor=self.owner, data={'expected_version': 1, 'recruitment_quota': 3})
        notes = self.client.get('/api/v1/notifications/?unread=true').json()['results']
        note = next(note for note in notes if note['kind'] == 'recruitment_edited')
        result = self.client.post(f"/api/v1/notifications/{note['id']}/read/", {}, format='json')
        self.assertEqual(result.status_code, 200)
        app.refresh_from_db()
        self.assertTrue(app.is_paused)
        self.assertEqual(app.current_revision.version, 1)
        self.client.force_authenticate(self.third)
        self.assertEqual(self.client.post(f"/api/v1/notifications/{note['id']}/read/", {}, format='json').status_code, 404)

    def test_database_open_filter_and_option_values(self):
        card = self.card(recruitment_quota=1)
        self.assertEqual(self.client.get('/api/v1/recruitments/?open_only=true&role=developer').json()['count'], 1)
        self.join(card)
        self.assertEqual(self.client.get('/api/v1/recruitments/?open_only=true').json()['count'], 0)
        self.assertEqual(self.client.get('/api/v1/recruitments/').json()['count'], 1)
        self.assertEqual(self.client.get('/api/v1/recruitments/options/').json()['roles'][0]['code'], 'developer')

    def test_competition_withdraw_service_keeps_joined_but_ends_pending(self):
        from django.contrib.auth.models import Permission
        from competitions.services import withdraw_competition
        self.owner.is_staff = True
        self.owner.save()
        self.owner.user_permissions.add(Permission.objects.get(codename='change_competition'))
        card = self.card()
        joined = self.join(card)
        pending = self.apply(card, self.third)
        self.action(pending, 'accept')
        withdraw_competition(self.competition.pk, actor=self.owner, reason='官方已停止该届赛事')
        pending.refresh_from_db()
        joined.refresh_from_db()
        card.refresh_from_db()
        self.assertEqual(card.close_reason, 'competition_withdrawn')
        self.assertEqual(pending.end_reason, 'competition_withdrawn')
        self.assertFalse(pending.can_view_contact(self.third.pk))
        self.assertTrue(joined.can_view_contact(self.student.pk))
        self.assertEqual(self.client.get(f'/api/v1/recruitments/{card.pk}/').status_code, 404)

    def test_admin_card_withdraw_only_ends_unjoined_relationships(self):
        from django.contrib.auth.models import Permission
        from governance.models import AdminAction
        self.owner.is_staff = True
        self.owner.save()
        self.owner.user_permissions.add(Permission.objects.get(codename='change_recruitment'))
        card = self.card()
        joined = self.join(card)
        pending = self.apply(card, self.third)
        self.action(pending, 'accept')
        s.withdraw_recruitment(card.pk, actor=self.owner, reason='经核实招募信息不准确')
        pending.refresh_from_db()
        self.assertEqual(pending.end_reason, 'card_withdrawn')
        self.assertFalse(pending.can_view_contact(self.third.pk))
        self.assertTrue(joined.can_view_contact(self.student.pk))
        self.assertEqual(AdminAction.objects.filter(recruitment=card, action='withdraw').count(), 1)
        self.assertEqual(self.client.get(f'/api/v1/recruitments/{card.pk}/').status_code, 404)

    def test_events_and_notifications_rollback_with_business_operation(self):
        card = self.card()
        with patch('notifications.services.Notification.save', side_effect=RuntimeError('simulated delivery persistence failure')):
            with self.assertRaises(RuntimeError):
                self.apply(card)
        self.assertEqual(Application.objects.count(), 0)
        self.assertEqual(BusinessEvent.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_seed_real_options_is_idempotent_and_preserves_disabled(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('seed_recruitment_options', stdout=StringIO())
        option = RecruitmentOption.objects.get(code='role-development')
        option.is_active = False
        s.save(option)
        count = RecruitmentOption.objects.count()
        call_command('seed_recruitment_options', stdout=StringIO())
        option.refresh_from_db()
        self.assertEqual(RecruitmentOption.objects.count(), count)
        self.assertFalse(option.is_active)

    def test_publication_restriction_blocks_new_only_existing_confirm_and_exit_work(self):
        card = self.card()
        app = self.apply(card)
        self.action(app, 'accept')
        now = timezone.now()
        s.save(UserRestriction(user=self.student, reason='测试新增操作限制', created_by=self.owner,
                               starts_at=now, expires_at=now + timedelta(hours=24)))
        other = self.card(actor=self.third)
        self.assert_conflict('account_ineligible', self.apply, other)
        self.action(app, 'confirm', self.student)
        self.action(app, 'confirm')
        member = Membership.objects.get(application=app)
        self.assertEqual(s.request_departure(member.pk, actor=self.student, kind='exit').status, 'pending')

    def test_changed_competition_deadline_is_shown_and_enforced_without_rewriting_card(self):
        from .serializers import card_output
        card = self.card()
        original_expiry = card.expires_at
        earlier = timezone.now() + timedelta(hours=2)
        with s.lock_competition_graph(self.competition.pk):
            self.competition.recruitment_deadline = earlier
            s.save(self.competition)
            s.reconcile_competition(self.competition.pk)
        card.refresh_from_db()
        self.assertEqual(card.expires_at, original_expiry)

        self.assertEqual(card_output(card)['effective_expires_at'], earlier)
        with patch('teams.services.timezone.now', return_value=earlier):
            self.assert_conflict('card_unavailable', self.apply, card)
        card.refresh_from_db()
        self.assertEqual(card.close_reason, 'competition_stopped')
        self.assertEqual(card.expires_at, original_expiry)

    def test_paused_application_still_allows_revoking_own_confirmation(self):
        card = self.card(recruitment_quota=3)
        self.join(card, self.third)
        app = self.apply(card)
        self.action(app, 'accept')
        self.action(app, 'confirm', self.student)
        s.request_dissolution(card.team_id, actor=self.owner)
        self.client.force_authenticate(self.student)
        result = self.client.get(f'/api/v1/applications/{app.pk}/')
        self.assertTrue(result.json()['is_paused'])
        self.assertIn('revoke-confirmation', result.json()['allowed_actions'])
        result = self.client.post(f'/api/v1/applications/{app.pk}/revoke-confirmation/',
            {'expected_version': 1, 'expected_application_version': 1}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertIsNone(result.json()['applicant_confirmed_at'])
        self.assertTrue(result.json()['is_paused'])

    def test_departed_user_sees_only_own_history_not_later_team_records(self):
        card = self.card(recruitment_quota=3)
        member = Membership.objects.get(application=self.join(card))
        own_exit = s.request_departure(member.pk, actor=self.student, kind='exit')
        s.departure_action(own_exit.pk, actor=self.owner, action='respond', response='agree')
        later_member = Membership.objects.get(application=self.join(card, self.third))
        later_exit = s.request_departure(later_member.pk, actor=self.third, kind='exit')
        later_dissolution = s.request_dissolution(card.team_id, actor=self.owner)
        self.client.force_authenticate(self.student)
        result = self.client.get(f'/api/v1/teams/{card.team_id}/').json()
        self.assertTrue(result['history_only'])
        self.assertEqual([m['id'] for m in result['memberships']], [member.pk])
        self.assertEqual([r['id'] for r in result['departure_requests']], [own_exit.pk])
        self.assertEqual(result['dissolution_requests'], [])
        self.assertEqual(result['recruitments'], [])
        self.assertEqual(result['allowed_actions'], [])
        self.client.force_authenticate(self.owner)
        current = self.client.get(f'/api/v1/teams/{card.team_id}/').json()
        self.assertFalse(current['history_only'])
        self.assertIn(later_member.pk, [m['id'] for m in current['memberships']])
        self.assertIn(later_exit.pk, [r['id'] for r in current['departure_requests']])
        self.assertIn(later_dissolution.pk, [r['id'] for r in current['dissolution_requests']])

    def test_confirmation_notifications_identify_actual_party_for_both_recipients(self):
        app = self.apply(self.card())
        self.action(app, 'accept')
        self.action(app, 'confirm', self.student)
        for user in (self.owner, self.student):
            self.client.force_authenticate(user)
            messages = self.client.get('/api/v1/notifications/').json()['results']
            confirmation = next(item for item in messages if item['kind'] == 'application_confirmed')
            self.assertEqual(confirmation['title'], '申请人已确认入队')
        self.action(app, 'revoke-confirmation', self.student)
        self.client.force_authenticate(self.student)
        latest = self.client.get('/api/v1/notifications/').json()['results'][0]
        self.assertEqual(latest['title'], '申请人已撤销本次确认')

    def test_only_explicit_seed_options_are_hidden_from_public_choices(self):
        s.save(RecruitmentOption(code='demo-r2-hidden', kind='role', name='【虚构样例】测试角色'))
        s.save(RecruitmentOption(code='demo-r2-real', kind='role', name='保留既有角色'))
        choices = self.client.get('/api/v1/recruitments/options/').json()['roles']
        self.assertNotIn('demo-r2-hidden', [item['code'] for item in choices])
        self.assertIn('demo-r2-real', [item['code'] for item in choices])
