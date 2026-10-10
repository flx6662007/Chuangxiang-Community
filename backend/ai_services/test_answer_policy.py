"""First-turn planning and evidence-aware answers, including empty retrieval and SSE."""
import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from .chat import chat, stream_chat
from .exceptions import AITimeoutError
from .test_chat import CHAT_SETTINGS
from .unified import _record


EMPTY = {'records': [], 'knowledge_rows': [], 'knowledge_status': 'no_published_knowledge',
         'mode_used': 'keyword', 'warnings': []}


def provider(question, kind='advice', text='可以先按兴趣选择方向，再了解赛制并尝试一个小项目。'):
    return Mock(spec=['complete_json', 'complete_text', 'stream_text'],
                complete_json=Mock(return_value={
                    'relation': 'new', 'question': question, 'kind': kind,
                    'search_scope': 'topic', 'target_indices': [], 'clarification': '',
                }), complete_text=Mock(return_value=text), stream_text=Mock(return_value=iter([text])))


@override_settings(PUBLIC_RESEARCH_ENABLED=True)
class AnswerPolicyTests(SimpleTestCase):
    def setUp(self):
        self.retrieval = patch('ai_services.chat.retrieve_unified', return_value=EMPTY).start()
        self.web = patch('ai_services.chat.search_external', return_value=([], 'external_search_unavailable')).start()
        self.addCleanup(patch.stopall)

    def test_first_turn_shortcuts_use_rewritten_question_and_generate_without_sources(self):
        cases = [
            ('smart', '竞赛入门', '大学生初次参加竞赛，如何选择方向和准备？', 'advice'),
            ('smart', 'AI 相关', '人工智能相关的竞赛有哪些可选择的方向？', 'fact'),
            ('smart', '适合大二学生', '适合大二学生的科创竞赛和学习资源有哪些？', 'fact'),
            ('smart', '科研创新类', '科研创新类的竞赛和科研项目有哪些选择方向？', 'fact'),
            ('resource', 'Python 入门', '初学者如何学习 Python，有什么学习资源？', 'advice'),
        ]
        for mode, question, rewritten, kind in cases:
            with self.subTest(question=question):
                client = provider(rewritten, kind)
                result = chat([{'role': 'user', 'content': question}], mode=mode,
                              client=client, details=True, web_search=False)
                client.complete_json.assert_called_once()
                client.complete_text.assert_called_once()
                self.assertEqual(self.retrieval.call_args.args[0], rewritten)
                payload = json.loads(client.complete_json.call_args.args[0][1]['content'])
                self.assertEqual(payload['conversation'], [{'role': 'user', 'content': question}])
                self.assertEqual(payload['server_context'], {})
                self.assertEqual(result['retrieval']['understanding'], 'model')
                self.assertEqual(result['sources'], [])
                self.assertEqual(result['recommendations'], [])
                self.assertIn('选择方向', result['message']['content'])
                self.assertIn(rewritten, client.complete_text.call_args.args[0][-2]['content'])
        self.web.assert_not_called()

    def test_planner_failure_on_first_turn_still_allows_general_answer(self):
        for failure in (AITimeoutError(), {}, {'question': '不完整计划'}):
            with self.subTest(failure=type(failure).__name__):
                client = provider('竞赛入门')
                if isinstance(failure, Exception):
                    client.complete_json.side_effect = failure
                else:
                    client.complete_json.return_value = failure
                result = chat([{'role': 'user', 'content': '竞赛入门'}], client=client,
                              details=True, web_search=False)
                self.assertEqual(result['retrieval']['understanding'], 'fallback')
                client.complete_text.assert_called_once()
                self.assertIn('通用知识', client.complete_text.call_args.args[0][0]['content'])

    def test_empty_fact_and_failed_web_are_explained_without_restoring_old_facts(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                client = provider('某机器人比赛今年报名截止日期？', 'fact', '未核实今年截止日期，请核对本届报名公告。')
                self.web.reset_mock()
                result = chat([{'role': 'user', 'content': '某机器人比赛今年报名截止日期？'}],
                              client=client, details=True, web_search=enabled)
                prompt = client.complete_text.call_args.args[0][0]['content']
                self.assertIn('具体事实', prompt)
                self.assertIn('未取得可用证据' if enabled else '关闭了联网搜索', prompt)
                self.assertEqual(self.web.call_count, int(enabled))
                self.assertEqual(result['sources'], [])

    def test_mixed_question_keeps_evidence_and_general_guidance(self):
        row = _record('competition', 'db-1', '机器人测试赛', '机器人竞赛', '项目包含视觉识别任务。',
                      'https://www.tongji.edu.cn/robot', source_type='platform_competition')
        self.retrieval.return_value = {**EMPTY, 'records': [row]}
        question = '机器人测试赛今年什么时候截止，我零基础怎么准备？'
        client = provider(question, 'fact', '该赛包含视觉识别任务。[1] 截止日期未核实。零基础可先学习编程和图像处理。')
        result = chat([{'role': 'user', 'content': question}], client=client, details=True, web_search=False)
        messages = client.complete_text.call_args.args[0]
        self.assertIn('其余可用通用知识回答的部分', messages[0]['content'])
        self.assertIn('项目包含视觉识别任务', messages[-2]['content'])
        self.assertIn('什么时候截止', messages[-2]['content'])
        self.assertEqual(len(result['sources']), 1)
        self.assertIn('[1]', result['message']['content'])

    def test_no_evidence_still_streams_and_finishes_with_empty_sources(self):
        client = provider('大学生如何入门竞赛？')
        client.stream_text.return_value = iter(['先选方向，', '再做小项目。'])
        events = list(stream_chat([{'role': 'user', 'content': '竞赛入门'}], client=client, web_search=False))
        self.assertEqual([kind for kind, _ in events], ['status', 'status', 'delta', 'delta', 'done'])
        self.assertEqual(events[-1][1]['message']['content'], '先选方向，再做小项目。')
        self.assertEqual(events[-1][1]['sources'], [])
        client.complete_text.assert_not_called()

    @override_settings(AI_CHAT=CHAT_SETTINGS)
    def test_production_factory_creates_bounded_planner_on_first_turn(self):
        planner = provider('大学生如何入门竞赛？')
        answer = provider('unused')
        with patch('ai_services.chat.OpenAICompatibleClient', side_effect=[planner, answer]) as factory:
            chat([{'role': 'user', 'content': '竞赛入门'}], details=True, web_search=False)
        planner.complete_json.assert_called_once()
        answer.complete_text.assert_called_once()
        self.assertEqual(factory.call_args_list[0].args[0].timeout_seconds, 12)
        self.assertEqual(factory.call_args_list[0].args[0].max_output_tokens, 768)

    @override_settings(PUBLIC_RESEARCH_ENABLED=False)
    def test_closed_research_records_are_not_exposed_by_general_fallback(self):
        client = provider('本科生科研机会', 'fact')
        result = chat([{'role': 'user', 'content': '本科生科研机会'}], mode='research',
                      client=client, details=True, web_search=True)
        self.assertIn('暂不开放', result['message']['content'])
        self.retrieval.assert_not_called()
        self.web.assert_not_called()
        client.complete_text.assert_not_called()
