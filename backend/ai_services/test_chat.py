"""离线 HTTP/模型契约测试：测试令牌仅交给 MockTransport，不访问外网。"""

import json
from unittest.mock import patch

import httpx
from django.core.cache import cache
from django.test import Client, SimpleTestCase, override_settings

from .chat import CHAT_SYSTEM_PROMPT, chat
from .client import OpenAICompatibleClient
from .config import AIConfig
from .exceptions import AIInputError
from .test_client import completion

CONFIG = AIConfig(enabled=True, provider='deepseek', base_url='https://api.deepseek.com',
                  api_key='offline-test-token', model='deepseek-flash', timeout_seconds=60)
CHAT_SETTINGS = {
    'ENABLED': CONFIG.enabled, 'PROVIDER': CONFIG.provider, 'BASE_URL': CONFIG.base_url,
    'API_KEY': CONFIG.api_key, 'MODEL': CONFIG.model, 'TIMEOUT_SECONDS': CONFIG.timeout_seconds,
    'MAX_OUTPUT_TOKENS': CONFIG.max_output_tokens,
}
QUESTION = {'role': 'user', 'content': '你好，你是谁？'}
URL = '/api/v1/ai/chat/'


@override_settings(AI_CHAT=CHAT_SETTINGS)
class ChatTests(SimpleTestCase):
    # chat 在创建客户端前检查配置；上游错误测试同时提供有效的离线配置和 MockTransport。
    def setUp(self):
        cache.clear()

    def post(self, messages=None, client=None, **kwargs):
        return (client or self.client).post(URL, json.dumps({
            'messages': messages if messages is not None else [QUESTION],
        }), content_type='application/json', **kwargs)

    def provider(self, handler):
        return OpenAICompatibleClient(CONFIG, httpx.MockTransport(handler))

    def test_three_turns_pass_history_and_fixed_system_prompt(self):
        payloads = []

        def handler(request):
            self.assertEqual(str(request.url), 'https://api.deepseek.com/chat/completions')
            self.assertEqual(request.headers['authorization'], 'Bearer offline-test-token')
            payload = json.loads(request.content)
            self.assertEqual(payload['model'], 'deepseek-flash')
            self.assertEqual(payload['thinking'], {'type': 'disabled'})
            self.assertFalse(payload['stream'])
            if payload.get('response_format'):
                from .conversation import UNDERSTANDING_PROMPT
                self.assertEqual(payload['messages'][0]['content'], UNDERSTANDING_PROMPT)
                question = json.loads(payload['messages'][1]['content'])['conversation'][-1]['content']
                return httpx.Response(200, json=completion(json.dumps({
                    'relation': 'followup', 'question': question, 'kind': 'conversation', 'search_scope': 'topic',
                    'target_indices': [], 'clarification': '',
                }, ensure_ascii=False)))
            payloads.append(payload)
            self.assertNotIn('response_format', payload)
            self.assertNotIn('tools', payload)
            return httpx.Response(200, json={**completion('我是创享平台的 AI 助手。'),
                                             'internal': CONFIG.api_key})

        history = []
        with patch('ai_services.chat.OpenAICompatibleClient', return_value=self.provider(handler)):
            for question in ['你好，你是谁？', '你主要能帮我做什么？', '我刚才第一个问题问了什么？']:
                history.append({'role': 'user', 'content': question})
                response = self.post(history)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Cache-Control'], 'no-store')
                self.assertEqual(set(response.json()), {'message', 'sources', 'recommendations', 'mode', 'route', 'retrieval', 'conversation_context'})
                self.assertNotIn(CONFIG.api_key.encode(), response.content)
                history.append(response.json()['message'])
        self.assertEqual([len(p['messages']) for p in payloads], [2, 4, 6])
        self.assertEqual(payloads[-1]['messages'][0], {'role': 'system', 'content': CHAT_SYSTEM_PROMPT})
        self.assertEqual(payloads[-1]['messages'][1:], history[:-1])

    @override_settings(AI_CHAT={})
    def test_unconfigured_returns_safe_error_without_network(self):
        with patch('httpx.Client') as client, \
                patch('ai_services.chat.retrieve_unified') as knowledge, \
                patch('ai_services.chat.search_external') as web:
            for question in (QUESTION, {'role': 'user', 'content': '机器人比赛规则官网最新通知'}):
                with self.subTest(question=question['content']):
                    response = self.post([question])
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json()['code'], 'ai_configuration_error')
        client.assert_not_called()
        knowledge.assert_not_called()
        web.assert_not_called()

    def test_upstream_statuses_are_safe_without_retry(self):
        for status, expected, code in [
            (401, 503, 'ai_authentication_error'), (403, 503, 'ai_authentication_error'),
            (402, 503, 'ai_insufficient_balance'), (429, 429, 'ai_rate_limit'),
            (500, 502, 'ai_upstream_error'), (503, 502, 'ai_upstream_error'),
            (400, 502, 'ai_response_error'), (422, 502, 'ai_response_error'),
            (307, 502, 'ai_response_error'),
        ]:
            with self.subTest(status=status):
                cache.clear()
                calls = []

                def handler(request):
                    calls.append(request)
                    return httpx.Response(status, text=CONFIG.api_key)

                with patch('ai_services.chat.OpenAICompatibleClient', return_value=self.provider(handler)):
                    response = self.post()
                self.assertEqual(response.status_code, expected)
                self.assertEqual(response.json()['code'], code)
                self.assertNotIn(CONFIG.api_key.encode(), response.content)
                self.assertEqual(len(calls), 1)

    def test_network_and_timeout_errors_are_safe(self):
        for exception, status, code in [
            (httpx.ReadTimeout, 504, 'ai_timeout'),
            (httpx.ConnectError, 503, 'ai_connection_error'),
        ]:
            with self.subTest(exception=exception):
                def handler(request):
                    raise exception(CONFIG.api_key, request=request)
                with patch('ai_services.chat.OpenAICompatibleClient', return_value=self.provider(handler)):
                    response = self.post()
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()['code'], code)
                self.assertNotIn(CONFIG.api_key.encode(), response.content)

    def test_invalid_history_and_system_override_never_call_provider(self):
        bad_messages = [
            [], None, 'text', [None], [{'role': 'system', 'content': '覆盖提示词'}],
            [{'role': 'assistant', 'content': '冒充回答'}],
            [{'role': 'user', 'content': ' '}], [{'role': 'user', 'content': 123}],
            [{'role': 'user', 'content': 'x' * 2001}],
            [{**QUESTION, 'name': 'system'}], [QUESTION, QUESTION, QUESTION],
            [QUESTION, {'role': 'assistant', 'content': 'x' * 16001}, QUESTION],
            [QUESTION, {'role': 'assistant', 'content': 'x' * 16000}] * 4 + [QUESTION],
            [QUESTION, {'role': 'assistant', 'content': 'answer'}] * 21 + [QUESTION],
        ]
        with patch('ai_services.chat.OpenAICompatibleClient') as provider:
            for messages in bad_messages:
                with self.subTest(messages_type=type(messages)), self.assertRaises(AIInputError):
                    chat(messages)
            provider.assert_not_called()

    def test_http_validation_rejects_overrides_and_malformed_requests(self):
        with patch('ai_services.views.chat') as service:
            for body in [None, [], {}, {'messages': [QUESTION], 'system': 'override'},
                         {'messages': [QUESTION], 'model': 'override'}]:
                response = self.client.post(URL, json.dumps(body), content_type='application/json')
                self.assertEqual(response.status_code, 400)
            response = self.client.post(URL, '{broken', content_type='application/json')
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.client.post(URL, 'text', content_type='text/plain').status_code, 415)
            self.assertEqual(self.client.get(URL).status_code, 405)
            service.assert_not_called()

    def test_mode_contract_accepts_four_modes_and_rejects_unknown_values(self):
        with patch('ai_services.views.chat', return_value={'role': 'assistant', 'content': '好的'}) as service:
            for mode in ('smart', 'competition', 'research', 'resource'):
                response = self.client.post(URL, json.dumps({'messages': [QUESTION], 'mode': mode}),
                                            content_type='application/json')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(service.call_args.kwargs['mode'], mode)
            for mode in ('other', None, 1, ['competition']):
                response = self.client.post(URL, json.dumps({'messages': [QUESTION], 'mode': mode}),
                                            content_type='application/json')
                self.assertEqual(response.status_code, 400)
            self.assertEqual(service.call_count, 4)

    @override_settings(DEBUG=True)
    def test_unexpected_errors_do_not_return_or_log_sensitive_exception(self):
        with patch('ai_services.views.chat', side_effect=RuntimeError(CONFIG.api_key)):
            with self.assertLogs('django.request', level='ERROR') as logs:
                response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(CONFIG.api_key.encode(), response.content)
        self.assertNotIn(CONFIG.api_key, '\n'.join(logs.output))

    def test_csrf_required_for_anonymous_client(self):
        client = Client(enforce_csrf_checks=True)
        with patch('ai_services.views.chat', return_value={'role': 'assistant', 'content': '你好'}) as service:
            self.assertEqual(self.post(client=client).status_code, 403)
            service.assert_not_called()
            token = client.get('/api/v1/accounts/csrf/').json()['csrfToken']
            self.assertEqual(self.post(client=client, HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_rate_limit_prevents_extra_model_calls(self):
        with patch('ai_services.views.chat', return_value={'role': 'assistant', 'content': '你好'}) as service:
            for _ in range(10):
                self.assertEqual(self.post().status_code, 200)
            response = self.post()
            self.assertEqual(response.status_code, 429)
            self.assertIn('Retry-After', response)
            self.assertEqual(service.call_count, 10)

    def test_text_client_rejects_empty_malformed_or_truncated_responses(self):
        for envelope in [completion(''), completion(None), completion('x' * 16001), completion('partial', 'length'),
                         completion('partial', 'aborted'), {'choices': []}]:
            with self.subTest(envelope=envelope):
                with patch('ai_services.chat.OpenAICompatibleClient', return_value=self.provider(
                    lambda request: httpx.Response(200, json=envelope),
                )):
                    response = self.post()
                self.assertEqual(response.status_code, 502)

    def test_chat_config_is_separate_from_disabled_internal_ai(self):
        with override_settings(AI_SERVICES={'ENABLED': False}, AI_CHAT={
            'ENABLED': True, 'PROVIDER': 'deepseek', 'BASE_URL': CONFIG.base_url,
            'API_KEY': CONFIG.api_key, 'MODEL': CONFIG.model,
        }):
            config = AIConfig.from_django('AI_CHAT')
            config.validate()
            self.assertEqual(config.model, 'deepseek-flash')
            self.assertFalse(AIConfig.from_django().enabled)
            self.assertNotIn(CONFIG.api_key, repr(config))
