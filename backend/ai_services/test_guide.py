from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, Client, override_settings
from django.utils import timezone

from .guide import run_guide, recruitment_matches, GuideInput, understand


def corpus():
    source = {'id': 's1', 'title': '赛事章程', 'url': 'https://example.org/rules', 'quote': '本科生，三人队', 'locator': '参赛要求', 'verified_at': '2026-10-01'}
    record = {'id': 'robot-guide', 'code': 'robot-guide', 'title': '机器人比赛', 'summary': '机器人与程序设计', 'edition': '2025届',
              'catalog_code': '2026001', 'catalog_codes': ['2026001'], 'aliases': ['机器人'], 'level': 'national',
              'content_hash': 'fixture-v1', 'review_status': 'approved', 'publication_status': 'published',
              'fields': {'education': ['本科'], 'team_size_min': 3, 'team_size_max': 3},
              'field_evidence': {'education': ['s1'], 'team_size_min': ['s1'], 'team_size_max': ['s1']},
              'sources': [source], 'sections': [{'id': 'rules', 'heading': '参赛要求', 'text': '机器人比赛面向本科生，三人组队，制作机器人。', 'evidence_ids': ['s1']}]}
    return {'schema_version': 1, 'version': 'fixture-corpus', 'records': [record]}


@override_settings(AI_CHAT={'ENABLED': False})
class GuideTests(SimpleTestCase):
    def test_profile_followup_and_ordinal_preserve_selection(self):
        state, answer = run_guide({'action': 'search', 'message': '我是大二学生，想了解机器人比赛，每周能投入5小时'}, corpus=corpus())
        self.assertEqual(state['profile']['weekly_hours'], 5)
        self.assertEqual(len(answer['candidates']), 1)
        state, answer = run_guide({'action': 'search', 'message': '分析第一个'}, state, corpus=corpus())
        self.assertEqual(answer['selected']['record_id'], 'robot-guide')
        self.assertEqual(answer['selected']['match_status'], 'unknown')
        self.assertEqual(state['profile']['grade'], '大二')

    def test_conflicting_team_size_excluded_and_unknown_not_called_eligible(self):
        _, answer = run_guide({'action': 'search', 'message': '机器人', 'profile': {'team_size': 99}}, corpus=corpus())
        self.assertEqual(answer['candidates'], [])
        _, answer = run_guide({'action': 'search', 'message': '机器人', 'profile': {'major': '计算机'}}, corpus=corpus())
        self.assertEqual(answer['candidates'][0]['match_status'], 'unknown')

    def test_current_registration_is_never_invented_from_historical_material(self):
        _, answer = run_guide({'action': 'search', 'message': '机器人现在还能报名吗'}, corpus=corpus())
        self.assertEqual(answer['candidates'], [])
        self.assertEqual(answer['filters']['registration_status'], 'open')

    def test_new_hard_filter_clears_the_previously_selected_result(self):
        previous = {'query': '机器人', 'selected': 'robot-guide', 'profile': {}}
        _, answer = run_guide({'action': 'search', 'filters': {'registration_status': 'open'}}, previous, corpus=corpus())
        self.assertEqual(answer['candidates'], [])
        self.assertIsNone(answer['selected'])

    def test_model_cannot_attach_an_unrelated_value_to_a_real_quote(self):
        class Model:
            def complete_json(self, messages):
                return {'query': '机器人', 'profile': {'major': '医学'}, 'evidence': {'major': '机器人'}}
        profile, _, _ = understand('机器人', client=Model())
        self.assertNotIn('major', profile)

    def test_selected_document_withdrawal_rechecked_on_restore(self):
        data = corpus()
        previous = {'query': '机器人', 'selected': 'robot-guide', 'profile': {}}
        data['records'][0]['review_status'] = 'withdrawn'
        state, answer = run_guide({'action': 'restore'}, previous, corpus=data)
        self.assertIsNone(answer['selected'])
        self.assertEqual(state['selected'], '')

    def test_model_without_supporting_user_quote_cannot_invent_profile(self):
        class Model:
            def complete_json(self, messages):
                return {'query': '机器人', 'profile': {'major': '医学', 'skills': ['Python']}, 'evidence': {'major': '我是医学专业'}}
        profile, query, mode = understand('机器人', client=Model())
        self.assertNotIn('major', profile)
        self.assertNotIn('skills', profile)

    def test_negated_skill_is_not_added_and_invalid_fields_rejected(self):
        profile, _, _ = understand('我不会Python')
        self.assertNotIn('skills', profile)
        self.assertFalse(GuideInput(data={'profile': {'admin': True}}).is_valid())
        self.assertFalse(GuideInput(data={'filters': {'team_size': -1}}).is_valid())

    def test_changing_interests_updates_query_without_mutating_previous_state(self):
        previous = {'query': '机器人', 'profile': {'interests': ['机器人']}, 'selected': 'robot-guide'}
        state, _ = run_guide({'action': 'search', 'profile': {'interests': ['数学建模']}}, previous, corpus=corpus())
        self.assertEqual(state['query'], '数学建模')
        self.assertEqual(previous['profile']['interests'], ['机器人'])
        self.assertEqual(state['selected'], '')


@override_settings(AI_CHAT={'ENABLED': False})
class GuideHTTPTests(TestCase):
    @patch('ai_services.guide.database_corpus', side_effect=corpus)
    def test_csrf_session_restore_reset_and_other_browser_isolation(self, _):
        client = Client(enforce_csrf_checks=True)
        url = '/api/v1/ai/guide/'
        self.assertEqual(client.post(url, {}, content_type='application/json').status_code, 403)
        client.get('/api/v1/accounts/csrf/')
        headers = {'HTTP_X_CSRFTOKEN': client.cookies['csrftoken'].value}
        response = client.post(url, {'message': '机器人', 'profile': {'weekly_hours': 5}}, content_type='application/json', **headers)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(client.get(url).json()['profile']['weekly_hours'], 5)
        self.assertEqual(Client().get(url).json()['profile'], {})
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        client.post(url, {'action': 'reset'}, content_type='application/json', **headers)
        self.assertEqual(client.get(url).json()['profile'], {})


class GuideRecruitmentTests(TestCase):
    def setUp(self):
        from teams import test_services as fixtures
        self.user = lambda name: fixtures.TeamFlowTests.user(self, name)
        fixtures.TeamFlowTests.setUp(self)
        self.card_data = lambda **kw: fixtures.TeamFlowTests.card_data(self, **kw)
        self.card = lambda **kw: fixtures.TeamFlowTests.card(self, **kw)
        from competition_catalog.models import CatalogEntry, CatalogBinding
        entry = CatalogEntry.objects.create(code='2026001', version=2026, name='机器人比赛', grade='A', levels='全国', source_url='https://example.org/catalog')
        CatalogBinding.objects.create(entry=entry, competition=self.competition, basis='测试映射')
        self.record = corpus()['records'][0]
        self.record['edition'] = self.competition.edition

    def test_existing_open_recruitment_is_returned_without_contact_details(self):
        self.card(required_skills=['python'])
        rows = recruitment_matches(self.record, {'weekly_hours': 5, 'skills': ['Python']}, self.student)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['skills_to_confirm'], [])
        self.assertNotIn('email', str(rows))
        self.assertTrue(rows[0]['url'].startswith('/teams/'))

    def test_wrong_edition_insufficient_hours_and_expired_cards_are_excluded(self):
        card = self.card()
        self.assertEqual(recruitment_matches(self.record, {'weekly_hours': 1}), [])
        wrong = dict(self.record, edition='2024届')
        self.assertEqual(recruitment_matches(wrong, {}), [])
        with patch('django.utils.timezone.now', return_value=card.expires_at + timedelta(seconds=1)):
            self.assertEqual(recruitment_matches(self.record, {}), [])

    def test_next_edition_does_not_return_previous_edition_recruitment(self):
        self.card()
        self.record['fields']['registration_deadline'] = (timezone.localdate()-timedelta(days=1)).isoformat()
        self.assertEqual(recruitment_matches(self.record, {}), [])

    def test_team_actions_preselect_edition_and_own_team_is_not_recommended(self):
        from .guide import team_context
        card=self.card()
        context=team_context(self.record)
        self.assertEqual(context['create_url'],f'/teams/publish?competition_id={self.competition.pk}')
        self.assertEqual(recruitment_matches(self.record,{},self.owner),[])
        self.assertEqual(len(recruitment_matches(self.record,{},self.student)),1)

    @override_settings(AI_CHAT={'ENABLED':False})
    def test_guide_to_existing_application_and_two_party_confirmation(self):
        from teams import services
        from .guide import team_context
        card=self.card(required_skills=['python'])
        data=corpus();data['records']=[self.record]
        with patch('ai_services.guide.database_corpus',return_value=data):
            state,result=run_guide({'action':'teammates','record_id':self.record['id'],'profile':{'skills':['Python'],'weekly_hours':5}},user=self.student)
        self.assertEqual(result['recruitments'][0]['id'],card.pk)
        self.assertEqual(result['team_context']['competition']['id'],self.competition.pk)
        app=services.submit_application(card.pk,actor=self.student,data={'expected_version':card.current_revision.version,'weekly_effort':'over_2_to_5','desired_roles':['developer'],'skills':['python']})
        for action,actor in [('accept',self.owner),('confirm',self.student),('confirm',self.owner)]:
            app.refresh_from_db()
            services.application_action(app.pk,actor=actor,action=action,data={'expected_version':card.current_revision.version,'expected_application_version':app.current_revision.version})
        from teams.models import Membership
        self.assertTrue(Membership.objects.filter(competition=self.competition,user=self.student,ended_at__isnull=True).exists())
        self.assertEqual(recruitment_matches(self.record,{},self.student),[])
