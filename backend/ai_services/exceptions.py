"""模型调用的统一异常；调用方用 code 分类，不读取上游原始错误。"""


class AIServiceError(Exception):
    code = "ai_service_error"
    retryable = False
    default_message = "AI 服务暂时无法完成处理。"

    def __init__(self, message=None):
        super().__init__(message or self.default_message)


class AIConfigurationError(AIServiceError):
    code = "ai_configuration_error"
    default_message = "AI 服务未启用或配置不完整，请联系管理员。"


class AIInputError(AIServiceError):
    code = "ai_input_error"
    default_message = "提交给 AI 的内容不符合要求。"


class AITimeoutError(AIServiceError):
    code = "ai_timeout"
    retryable = True
    default_message = "AI 服务响应超时，可稍后重新发起。"


class AIConnectionError(AIServiceError):
    code = "ai_connection_error"
    retryable = True
    default_message = "暂时无法连接 AI 服务，可稍后重新发起。"


class AIAuthenticationError(AIServiceError):
    code = "ai_authentication_error"
    default_message = "AI 服务认证失败，请管理员检查密钥和权限。"


class AIRateLimitError(AIServiceError):
    code = "ai_rate_limit"
    retryable = True
    default_message = "AI 服务暂时限制调用，请稍后重新发起并检查额度。"


class AIUpstreamError(AIServiceError):
    code = "ai_upstream_error"
    retryable = True
    default_message = "模型服务暂时异常，可稍后重新发起。"


class AIResponseError(AIServiceError):
    code = "ai_response_error"
    default_message = "模型未返回完整、有效的 JSON 对象，本次结果不予使用。"


class AIValidationError(AIServiceError):
    code = "ai_validation_error"
    default_message = "模型结果未通过字段或来源校验，本次结果不予使用。"
