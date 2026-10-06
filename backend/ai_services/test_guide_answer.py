from copy import deepcopy
import json
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, override_settings
from .test_guide import corpus
from .guide import run_guide
from .guide_answer import compose_answer, build_context
from .exceptions import AITimeoutError

@override_settings(AI_CHAT={'ENABLED':False})
class AnswerTests(SimpleTestCase):
    def setUp(self):
        self.records = {r['id']:r for r in corpus()['records']}
        self.state,self.result = run_guide({'action':'analyze','record_id':'robot-guide'},corpus=corpus())
    def model(self):
        model=Mock()
        model.complete_json.return_value={'paragraphs':[{'text':'这项机器人比赛面向本科生，可以从机器人制作入手。','evidence_ids':['e3']}]}
        return model
    def test_citations_resolved_from_server_and_rendered_as_data(self):
        answer=compose_answer(self.result,self.records,'怎么准备',client=self.model())
        self.assertEqual(answer['mode'],'model')
        self.assertEqual(answer['paragraphs'][0]['citations'][0]['url'],'https://example.org/rules')
    def test_unknown_reference_url_and_invented_number_fall_back(self):
        for row in ({'text':'可报名','evidence_ids':['fake']}, {'text':'https://evil.com','evidence_ids':['e3']},
                    {'text':'报名截止为2099-10-10','evidence_ids':['e3']}):
            model=self.model();model.complete_json.return_value={'paragraphs':[row]}
            self.assertEqual(compose_answer(self.result,self.records,'准备',client=model)['mode'],'rules')
    def test_timeout_keeps_rules_and_can_retry(self):
        model=self.model();model.complete_json.side_effect=AITimeoutError()
        answer=compose_answer(self.result,self.records,'准备',client=model)
        self.assertEqual(answer['paragraphs'],[])
        self.assertTrue(answer['notice'])
    def test_restore_does_not_call_model_and_version_change_invalidates_answer(self):
        model=self.model()
        state,result=run_guide({'action':'analyze','record_id':'robot-guide'},corpus=corpus(),answer_client=model)
        _, restored=run_guide({'action':'restore'},state,corpus=corpus(),answer_client=model)
        self.assertEqual(restored['answer']['mode'],'model')
        self.assertEqual(model.complete_json.call_count,1)
        changed=corpus();changed['version']='changed'
        _,restored=run_guide({'action':'restore'},state,corpus=changed,answer_client=model)
        self.assertEqual(restored['answer']['paragraphs'],[])
        self.assertEqual(model.complete_json.call_count,1)
    def test_followup_registration_question_preserves_selected_competition(self):
        extractor=Mock();extractor.complete_json.return_value={'query':'报名','profile':{},'evidence':{}}
        _,result=run_guide({'action':'search','message':'这个比赛还能报名吗'},self.state,corpus=corpus(),client=extractor)
        self.assertEqual(result['selected']['record_id'],'robot-guide')
        self.assertNotIn('registration_status',result['filters'])
    def test_model_context_omits_contact_and_actor_actions(self):
        result=deepcopy(self.result);result['stage']='teammates'
        result['recruitments']=[dict(competition={'title':'比赛','edition':'2026'},remaining_slots=2,
            required_roles=[],required_skills=[],weekly_effort='up_to_2',collaboration_mode='online',
            match_reasons=[],skills_to_confirm=[],email='PRIVATE',allowed_actions=['PRIVATE'])]
        self.assertNotIn('PRIVATE',json.dumps(build_context(result,self.records,'队友')))

    def test_retry_preserves_question(self):
        state, _ = run_guide({'action':'analyze','record_id':'robot-guide','message':'这个比赛怎么准备'}, corpus=corpus(), answer_client=self.model())
        model = self.model()
        retried, result = run_guide({'action':'retry'}, state, corpus=corpus(), answer_client=model)
        self.assertEqual(retried['question'], state['question'])
        self.assertEqual(result['selected']['record_id'], 'robot-guide')
        self.assertEqual(model.complete_json.call_count, 1)

    def test_withdrawn_during_model_call_is_removed_before_return(self):
        initial = corpus()
        withdrawn = deepcopy(initial)
        withdrawn['version'] = 'withdrawn'
        withdrawn['records'] = []
        with patch('ai_services.guide.database_corpus', side_effect=[initial, withdrawn, withdrawn]), patch('ai_services.guide.team_context', return_value={}):
            _, result = run_guide({'action':'analyze','record_id':'robot-guide'}, answer_client=self.model())
        self.assertIsNone(result['selected'])
        self.assertEqual(result['answer']['paragraphs'], [])

    def test_teammate_context_does_not_reuse_historical_rules(self):
        result = deepcopy(self.result)
        result.update(stage='teammates', recruitments=[])
        context = build_context(result, self.records, '找队友')
        self.assertTrue(all(not row['sources'] for row in context['evidence']))
