"""集中调用 OpenAI 兼容的 Chat Completions 接口，不自动重试。"""

import json
import math

import httpx

from .config import AIConfig
from .exceptions import (
    AIAuthenticationError, AIConfigurationError, AIConnectionError,
    AIInputError, AIRateLimitError, AIResponseError, AITimeoutError,
    AIUpstreamError,
)


MAX_RESPONSE_BYTES = 256 * 1024


def _reject_constant(value):
    raise ValueError


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError
    return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _parse_json_object(content):
    try:
        value = json.loads(
            content, parse_constant=_reject_constant, parse_float=_finite_float,
            object_pairs_hook=_unique_object,
        )
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise AIResponseError() from None
    if not isinstance(value, dict):
        raise AIResponseError() from None
    return value


class OpenAICompatibleClient:
    def __init__(self, config=None, transport=None):
        self._config = config
        self._transport = transport

    def complete_json(self, messages: list[dict[str, str]]) -> dict:
        config = self._config if self._config is not None else AIConfig.from_django()
        if not isinstance(config, AIConfig):
            raise AIConfigurationError() from None
        config.validate()
        if not isinstance(messages, list) or not messages:
            raise AIInputError() from None
        for message in messages:
            if (
                not isinstance(message, dict)
                or set(message) != {"role", "content"}
                or message["role"] not in ("system", "user", "assistant")
                or not isinstance(message["content"], str)
                or not message["content"].strip()
            ):
                raise AIInputError() from None

        payload = {
            "model": config.model,
            "messages": messages,
            "stream": False,
            "response_format": {"type": "json_object"},
            "max_tokens": config.max_output_tokens,
        }
        if config.provider == "qwen":
            payload["enable_thinking"] = False

        try:
            # 每次调用释放连接；所有阶段都有超时，密钥不随重定向发送。
            with httpx.Client(
                timeout=httpx.Timeout(config.timeout_seconds),
                transport=self._transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                with client.stream(
                    "POST", config.endpoint,
                    headers={"Authorization": f"Bearer {config.api_key}"},
                    json=payload,
                ) as response:
                    if response.status_code in (401, 403):
                        raise AIAuthenticationError() from None
                    if response.status_code == 429:
                        raise AIRateLimitError() from None
                    if response.status_code >= 500:
                        raise AIUpstreamError() from None
                    if response.status_code != 200:
                        raise AIResponseError() from None
                    chunks = bytearray()
                    for chunk in response.iter_bytes():
                        if len(chunks) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise AIResponseError() from None
                        chunks.extend(chunk)
        except httpx.TimeoutException:
            raise AITimeoutError() from None
        except httpx.RequestError:
            raise AIConnectionError() from None
        except (httpx.InvalidURL, UnicodeError):
            raise AIConfigurationError() from None

        envelope = _parse_json_object(bytes(chunks))
        if envelope.get("error"):
            raise AIResponseError() from None
        choices = envelope.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise AIResponseError() from None
        choice = choices[0]
        if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
            raise AIResponseError() from None
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise AIResponseError() from None
        if any(message.get(field) is not None for field in ("tool_calls", "function_call", "refusal")):
            raise AIResponseError() from None
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AIResponseError() from None
        return _parse_json_object(content)
