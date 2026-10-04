"""聊天业务入口；当前仅使用本次请求的历史消息，不检索、不写入数据库。"""

from .client import OpenAICompatibleClient
from .config import AIConfig
from .exceptions import AIInputError, AIResponseError

CHAT_SYSTEM_PROMPT = """你是‘创享平台’的高校科创 AI 助手，主要帮助大学生了解学科竞赛、科研项目、创新创业、科研资源和团队协作。

当前版本尚未接入创享平台实时数据库和外部实时检索系统。因此，对于具体赛事日期、报名要求、平台内部项目、实时政策等可能变化的信息，不要假装已经查询过平台数据库或实时互联网。

如果信息无法确认，应明确说明，并提醒用户后续可以通过平台正式数据或官方来源核实。

回答应清晰、简洁、有帮助，优先围绕大学生科创场景。"""

MAX_MESSAGES = 41  # 最近 20 轮已完成对话 + 本次问题。
MAX_CONTEXT_CHARS = 60000
MAX_USER_CHARS = 2000
MAX_ASSISTANT_CHARS = 16000


def validate_chat_messages(messages):
    if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_MESSAGES:
        raise AIInputError()
    if len(messages) % 2 != 1:
        raise AIInputError()
    result = []
    for index, message in enumerate(messages):
        role = 'user' if index % 2 == 0 else 'assistant'
        limit = MAX_USER_CHARS if role == 'user' else MAX_ASSISTANT_CHARS
        if (
            not isinstance(message, dict)
            or set(message) != {'role', 'content'}
            or message['role'] != role
            or not isinstance(message['content'], str)
            or not message['content'].strip()
            or len(message['content']) > limit
        ):
            raise AIInputError()
        result.append({'role': role, 'content': message['content'].strip()})
    if sum(len(message['content']) for message in result) > MAX_CONTEXT_CHARS:
        raise AIInputError()
    return result


def chat(messages, *, client=None):
    history = validate_chat_messages(messages)
    provider = client if client is not None else OpenAICompatibleClient(
        AIConfig.from_django('AI_CHAT'),
    )
    content = provider.complete_text([
        {'role': 'system', 'content': CHAT_SYSTEM_PROMPT}, *history,
    ])
    if not isinstance(content, str) or not content.strip() or len(content) > MAX_ASSISTANT_CHARS:
        raise AIResponseError()
    return {'role': 'assistant', 'content': content}
