"""只使用 MockTransport；测试不会访问模型服务或产生调用费用。"""

import json
import traceback
from dataclasses import replace

import httpx
from django.test import SimpleTestCase, override_settings

from .client import MAX_RESPONSE_BYTES, OpenAICompatibleClient
from .config import AIConfig
from .exceptions import (
    AIAuthenticationError, AIConfigurationError, AIConnectionError,
    AIInputError, AIRateLimitError, AIResponseError, AITimeoutError,
    AIUpstreamError,
)


CONFIG = AIConfig(
    enabled=True, provider="qwen", base_url="https://model.test/v1/",
    api_key="unit-test-secret", model="test-model", timeout_seconds=15,
    max_output_tokens=512,
)
MESSAGES = [{"role": "user", "content": "请返回 JSON 对象。"}]


def completion(content='{"title":"测试赛事"}', finish_reason="stop", **message_fields):
    return {
        "choices": [{
            "finish_reason": finish_reason,
            "message": {"role": "assistant", "content": content, **message_fields},
        }],
    }


class AIClientTests(SimpleTestCase):
    def model_client(self, handler, config=CONFIG):
        return OpenAICompatibleClient(config, httpx.MockTransport(handler))

    def test_qwen_request_and_valid_result(self):
        def handler(request):
            self.assertEqual(str(request.url), "https://model.test/v1/chat/completions")
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.headers["authorization"], "Bearer unit-test-secret")
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], "test-model")
            self.assertEqual(payload["messages"], MESSAGES)
            self.assertEqual(payload["max_tokens"], 512)
            self.assertEqual(payload["response_format"], {"type": "json_object"})
            self.assertIs(payload["stream"], False)
            self.assertIs(payload["enable_thinking"], False)
            self.assertEqual(set(request.extensions["timeout"].values()), {15})
            return httpx.Response(200, json=completion())

        self.assertEqual(self.model_client(handler).complete_json(MESSAGES), {"title": "测试赛事"})

    def test_generic_provider_omits_qwen_option(self):
        def handler(request):
            self.assertNotIn("enable_thinking", json.loads(request.content))
            return httpx.Response(200, json=completion())

        self.model_client(handler, replace(CONFIG, provider="openai_compatible")).complete_json(MESSAGES)

    def test_http_error_categories_and_no_retry(self):
        for status, error in (
            (401, AIAuthenticationError), (403, AIAuthenticationError),
            (429, AIRateLimitError), (500, AIUpstreamError),
            (503, AIUpstreamError), (400, AIResponseError), (404, AIResponseError),
        ):
            with self.subTest(status=status):
                calls = []

                def handler(request):
                    calls.append(request)
                    return httpx.Response(status, text=CONFIG.api_key)

                with self.assertRaises(error) as raised:
                    self.model_client(handler).complete_json(MESSAGES)
                self.assertNotIn(CONFIG.api_key, str(raised.exception))
                self.assertEqual(len(calls), 1)

    def test_network_exceptions_are_safe_and_categorized(self):
        for transport_error, expected in (
            (httpx.ConnectTimeout, AITimeoutError),
            (httpx.ReadTimeout, AITimeoutError),
            (httpx.WriteTimeout, AITimeoutError),
            (httpx.ConnectError, AIConnectionError),
            (httpx.RemoteProtocolError, AIConnectionError),
        ):
            with self.subTest(error=transport_error):
                def handler(request):
                    raise transport_error(CONFIG.api_key, request=request)

                try:
                    self.model_client(handler).complete_json(MESSAGES)
                except expected as error:
                    # raise from None 隐去上游异常消息和其中的敏感内容。
                    formatted = "".join(traceback.format_exception(error))
                    self.assertNotIn(CONFIG.api_key, formatted)
                    self.assertTrue(error.retryable)
                    self.assertIsNone(error.__cause__)
                else:
                    self.fail("应转换为统一 AI 异常")

    def test_redirect_is_not_followed(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            return httpx.Response(307, headers={"location": "https://other.test/collect"})

        with self.assertRaises(AIResponseError):
            self.model_client(handler).complete_json(MESSAGES)
        self.assertEqual(calls, [CONFIG.endpoint])

    def test_bad_generated_json_is_rejected(self):
        for content in (
            "", "not json", "[]", "null", '```json\n{}\n```',
            '{"x":1,"x":2}', '{"x":{"n":1,"n":2}}',
            '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}',
            None, [{"type": "text", "text": "{}"}],
        ):
            with self.subTest(content=content), self.assertRaises(AIResponseError):
                self.model_client(lambda request: httpx.Response(
                    200, json=completion(content),
                )).complete_json(MESSAGES)

    def test_truncated_refused_and_tool_output_is_rejected(self):
        for envelope in (
            completion("{}", "length"), completion("{}", "content_filter"),
            completion("{}", tool_calls=[{"id": "ignored"}]),
            completion("{}", tool_calls=[]),
            completion("{}", function_call={"name": "ignored"}),
            completion("{}", refusal="拒绝回答"),
            completion("{}", role="user"),
            {"choices": []}, {"choices": [None]},
            {"choices": [completion()["choices"][0]] * 2},
            {**completion(), "error": {"message": "failure"}},
        ):
            with self.subTest(envelope=envelope), self.assertRaises(AIResponseError):
                self.model_client(lambda request: httpx.Response(200, json=envelope)).complete_json(MESSAGES)

    def test_non_json_or_duplicate_envelope_is_rejected(self):
        for content in (b"<html>Error</html>", b'{"choices": [], "choices": []}', b"[]"):
            with self.subTest(content=content), self.assertRaises(AIResponseError):
                self.model_client(lambda request: httpx.Response(200, content=content)).complete_json(MESSAGES)

    def test_response_size_is_limited_and_stream_is_closed(self):
        class LargeStream(httpx.SyncByteStream):
            closed = False

            def __iter__(self):
                yield b" " * MAX_RESPONSE_BYTES
                yield b"x"

            def close(self):
                self.closed = True

        stream = LargeStream()
        with self.assertRaises(AIResponseError):
            self.model_client(lambda request: httpx.Response(200, stream=stream)).complete_json(MESSAGES)
        self.assertTrue(stream.closed)

    def test_bad_input_does_not_call_model(self):
        def handler(request):
            self.fail("无效输入不应发送网络请求")

        for messages in (None, [], ["text"], [{"role": "user", "content": ""}],
                         [{"role": "tool", "content": "x"}],
                         [{"role": "user", "content": "x", "extra": "x"}]):
            with self.subTest(messages=messages), self.assertRaises(AIInputError):
                self.model_client(handler).complete_json(messages)


class AIConfigTests(SimpleTestCase):
    def test_sensitive_values_are_excluded_from_repr(self):
        self.assertNotIn(CONFIG.api_key, repr(CONFIG))
        self.assertNotIn(CONFIG.base_url, repr(CONFIG))

    def test_config_is_frozen(self):
        from dataclasses import FrozenInstanceError

        with self.assertRaises(FrozenInstanceError):
            CONFIG.enabled = False

    @override_settings(AI_SERVICES={})
    def test_missing_configuration_fails_only_when_called(self):
        client = OpenAICompatibleClient()
        self.assertFalse(AIConfig.from_django().enabled)
        with self.assertRaises(AIConfigurationError):
            client.complete_json(MESSAGES)

    @override_settings(AI_SERVICES={
        "ENABLED": "1", "PROVIDER": "qwen", "BASE_URL": "https://model.test/v1",
        "API_KEY": "test-secret", "MODEL": "test-model",
        "TIMEOUT_SECONDS": "10.5", "MAX_OUTPUT_TOKENS": "2048",
    })
    def test_django_configuration_converts_environment_values(self):
        config = AIConfig.from_django()
        config.validate()
        self.assertEqual(config.timeout_seconds, 10.5)
        self.assertEqual(config.max_output_tokens, 2048)

    def test_invalid_configuration_is_rejected_without_network(self):
        changes = (
            {"enabled": False}, {"provider": "unsupported"}, {"provider": []},
            {"api_key": ""}, {"api_key": "replace-with-your-key"},
            {"api_key": "bad\nkey"}, {"api_key": "密钥"},
            {"model": ""}, {"model": "replace-with-model"},
            {"base_url": "http://model.test/v1"},
            {"base_url": "https://name:secret@model.test/v1"},
            {"base_url": "https://model.test/v1?key=secret"},
            {"base_url": "https://model.test/v1#fragment"},
            {"base_url": "https://{WorkspaceId}.model.test/v1"},
            {"base_url": "https://%7BWorkspaceId%7D.model.test/v1"},
            {"base_url": "https://model.test:99999/v1"},
            {"timeout_seconds": 0}, {"timeout_seconds": 121},
            {"timeout_seconds": float("nan")}, {"timeout_seconds": float("inf")},
            {"max_output_tokens": 0}, {"max_output_tokens": 8193},
            {"max_output_tokens": 2.5}, {"max_output_tokens": True},
        )

        def handler(request):
            self.fail("无效配置不应发送网络请求")

        for change in changes:
            with self.subTest(change=change), self.assertRaises(AIConfigurationError):
                OpenAICompatibleClient(
                    replace(CONFIG, **change), httpx.MockTransport(handler),
                ).complete_json(MESSAGES)

    def test_invalid_django_numbers_raise_safe_configuration_errors(self):
        for field, value in (
            ("TIMEOUT_SECONDS", "not-number"), ("TIMEOUT_SECONDS", True),
            ("MAX_OUTPUT_TOKENS", "2.5"), ("MAX_OUTPUT_TOKENS", 2.5),
            ("ENABLED", "maybe"),
        ):
            with self.subTest(field=field, value=value), override_settings(AI_SERVICES={field: value}):
                with self.assertRaises(AIConfigurationError):
                    AIConfig.from_django()
