"""只在主动调用 AI 时读取并检查配置，不影响普通 Django 启动。"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

from .exceptions import AIConfigurationError


def _is_placeholder(value):
    lowered = unquote(value).lower()
    return any(marker in lowered for marker in (
        "replace-with", "your-api", "your-model", "your-key", "your-host",
        "changeme", "change-me", "<", ">", "{", "}",
    )) or lowered in {"xxx", "sk-xxx"}


@dataclass(frozen=True)
class AIConfig:
    enabled: bool = False
    provider: str = "qwen"
    base_url: str = field(default="", repr=False)
    api_key: str = field(default="", repr=False)
    model: str = ""
    timeout_seconds: float = 30.0
    max_output_tokens: int = 2048

    @classmethod
    def from_django(cls):
        # 避免模块导入阶段访问设置，也不在代码中固定最终模型名称。
        from django.conf import settings

        values = getattr(settings, "AI_SERVICES", {})
        if not isinstance(values, Mapping):
            raise AIConfigurationError() from None
        enabled = values.get("ENABLED", False)
        if isinstance(enabled, str):
            if enabled.lower() not in {"1", "0", "true", "false"}:
                raise AIConfigurationError() from None
            enabled = enabled.lower() in {"1", "true"}
        timeout = values.get("TIMEOUT_SECONDS", 30)
        tokens = values.get("MAX_OUTPUT_TOKENS", 2048)
        try:
            if isinstance(timeout, bool) or isinstance(tokens, bool):
                raise ValueError
            timeout = float(timeout)
            # 不将 100.5 静默截断为 100。
            if isinstance(tokens, str):
                tokens = int(tokens)
            elif not isinstance(tokens, int):
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            raise AIConfigurationError() from None
        return cls(
            enabled=enabled,
            provider=values.get("PROVIDER", "qwen"),
            base_url=values.get("BASE_URL", ""),
            api_key=values.get("API_KEY", ""),
            model=values.get("MODEL", ""),
            timeout_seconds=timeout,
            max_output_tokens=tokens,
        )

    def validate(self):
        if (
            self.enabled is not True
            or not isinstance(self.provider, str)
            or self.provider not in {"qwen", "openai_compatible"}
        ):
            raise AIConfigurationError() from None
        for value in (self.base_url, self.api_key, self.model):
            if not isinstance(value, str) or not value.strip() or _is_placeholder(value):
                raise AIConfigurationError() from None
            if value != value.strip() or any(ord(char) < 32 for char in value):
                raise AIConfigurationError() from None
        # HTTP 请求头中的令牌应为可打印 ASCII，防止头部注入和编码异常。
        if (
            not self.api_key.isascii() or not self.api_key.isprintable()
            or any(char.isspace() for char in self.api_key)
        ):
            raise AIConfigurationError() from None
        try:
            parsed = urlsplit(self.base_url)
            port = parsed.port
            valid_url = (
                parsed.scheme == "https" and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None
                and not parsed.query and not parsed.fragment
                and "?" not in self.base_url and "#" not in self.base_url
                and not any(char.isspace() for char in self.base_url)
                and "\\" not in self.base_url
                and (port is None or 0 < port <= 65535)
            )
        except (ValueError, TypeError):
            valid_url = False
        if not valid_url:
            raise AIConfigurationError() from None
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not 0 < self.timeout_seconds <= 120
            or not math.isfinite(self.timeout_seconds)
            or type(self.max_output_tokens) is not int
            or not 0 < self.max_output_tokens <= 8192
        ):
            raise AIConfigurationError() from None

    @property
    def endpoint(self):
        return self.base_url.rstrip("/") + "/chat/completions"
