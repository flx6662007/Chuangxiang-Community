"""Streaming contract: actual upstream chunks, final evidence payload and safe errors."""
import json
from unittest.mock import patch

import httpx
from django.test import Client, SimpleTestCase, override_settings

from .client import OpenAICompatibleClient
from .config import AIConfig


CONFIG = AIConfig(enabled=True, provider='deepseek', base_url='https://model.test',
                  api_key='offline-test-token', model='test-model', timeout_seconds=10)


def frame(delta, finish_reason=None):
    return ('data: ' + json.dumps({'choices': [{'delta': delta, 'finish_reason': finish_reason}]}) + '\n\n').encode()


class Upstream(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False

    def __iter__(self):
        yield from self.chunks

    def close(self):
        self.closed = True


@override_settings(ALLOWED_HOSTS=['testserver'], AI_CHAT={
    'ENABLED': True, 'PROVIDER': 'deepseek', 'BASE_URL': CONFIG.base_url,
    'API_KEY': CONFIG.api_key, 'MODEL': CONFIG.model,
})
class StreamChatTests(SimpleTestCase):
    def test_client_forwards_real_upstream_chunks(self):
        upstream = Upstream([frame({'role': 'assistant'}), frame({'content': '根据'}),
                             frame({'content': '你的需求'}), frame({}, 'stop'), b'data: [DONE]\n\n'])

        def handler(request):
            payload = json.loads(request.content)
            self.assertIs(payload['stream'], True)
            self.assertEqual(payload['thinking'], {'type': 'disabled'})
            self.assertNotIn('response_format', payload)
            return httpx.Response(200, stream=upstream)

        client = OpenAICompatibleClient(CONFIG, httpx.MockTransport(handler))
        self.assertEqual(list(client.stream_text([{'role': 'user', 'content': '你好'}])), ['根据', '你的需求'])
        self.assertTrue(upstream.closed)

    def test_http_stream_has_deltas_and_final_structured_result(self):
        upstream = Upstream([frame({'content': '根据'}), frame({'content': '你的需求'}),
                             frame({}, 'stop'), b'data: [DONE]\n\n'])
        client = OpenAICompatibleClient(CONFIG, httpx.MockTransport(
            lambda request: httpx.Response(200, stream=upstream)))
        with patch('ai_services.chat.OpenAICompatibleClient', return_value=client):
            response = Client().post('/api/v1/ai/chat/stream/',
                                     json.dumps({'messages': [{'role': 'user', 'content': '你好'}]}),
                                     content_type='application/json')
            self.assertTrue(response.streaming)
            self.assertEqual(response['Content-Type'], 'text/event-stream; charset=utf-8')
            chunks = list(response.streaming_content)
        self.assertEqual(len(chunks), 5)
        self.assertIn('retrieving', chunks[0].decode())
        self.assertIn('generating', chunks[1].decode())
        self.assertTrue(chunks[2].decode().startswith('event: delta'))
        self.assertTrue(chunks[3].decode().startswith('event: delta'))
        done = json.loads(chunks[4].decode().split('data: ', 1)[1])
        self.assertEqual(done['message']['content'], '根据你的需求')
        self.assertEqual(set(done), {'message', 'sources', 'recommendations', 'mode', 'route', 'retrieval', 'conversation_context'})

    def test_truncated_upstream_finishes_with_safe_error_event(self):
        upstream = Upstream([frame({'content': '部分回答'})])
        client = OpenAICompatibleClient(CONFIG, httpx.MockTransport(
            lambda request: httpx.Response(200, stream=upstream)))
        with patch('ai_services.chat.OpenAICompatibleClient', return_value=client):
            response = Client().post('/api/v1/ai/chat/stream/',
                                     json.dumps({'messages': [{'role': 'user', 'content': '你好'}]}),
                                     content_type='application/json')
            chunks = b''.join(response.streaming_content).decode()
        self.assertIn('event: delta', chunks)
        self.assertIn('event: error', chunks)
        self.assertIn('ai_response_error', chunks)
        self.assertNotIn(CONFIG.api_key, chunks)

    def test_invalid_input_still_uses_json_error(self):
        response = Client().post('/api/v1/ai/chat/stream/', json.dumps({'messages': []}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'ai_input_error')

    def test_disconnect_closes_upstream_without_waiting_for_done(self):
        from .chat import stream_chat
        upstream = Upstream([frame({'content': '首段'}), frame({'content': '迟到'}), frame({}, 'stop'), b'data: [DONE]\n\n'])
        client = OpenAICompatibleClient(CONFIG, httpx.MockTransport(lambda request: httpx.Response(200, stream=upstream)))
        events = stream_chat([{'role': 'user', 'content': '你好'}], client=client)
        self.assertEqual(next(events)[0], 'status')
        self.assertEqual(next(events)[0], 'status')
        self.assertEqual(next(events), ('delta', {'content': '首段'}))
        events.close()
        self.assertTrue(upstream.closed)

    def test_close_before_retrieval_does_not_start_search(self):
        from .chat import stream_chat
        with patch('ai_services.chat._prepare_chat') as prepare:
            events = stream_chat([{'role': 'user', 'content': '你好'}])
            self.assertEqual(next(events)[0], 'status')
            events.close()
        prepare.assert_not_called()

    def test_http_response_close_propagates_to_model_stream(self):
        upstream = Upstream([frame({'content': '首段'}), frame({'content': '后续'}), frame({}, 'stop'), b'data: [DONE]\n\n'])
        client = OpenAICompatibleClient(CONFIG, httpx.MockTransport(lambda request: httpx.Response(200, stream=upstream)))
        with patch('ai_services.chat.OpenAICompatibleClient', return_value=client):
            response = Client().post('/api/v1/ai/chat/stream/', json.dumps({'messages': [{'role': 'user', 'content': '你好'}]}), content_type='application/json')
            iterator = iter(response.streaming_content)
            for _ in range(3):
                next(iterator)
            response.close()
        self.assertTrue(upstream.closed)
