"""业务调用入口：校验输入 → 调用模型 → 校验输出，仅返回候选结果。"""

from .client import OpenAICompatibleClient
from .prompts import newsletter_messages, notice_messages
from .validators import (
    validate_newsletter_input,
    validate_newsletter_result,
    validate_notice_input,
    validate_notice_result,
)


def extract_notice(source_text, source_url, *, client=None):
    """从已取得的通知正文提取字段；不抓取网址、不入库、不发布。"""
    validate_notice_input(source_text, source_url)
    client = client if client is not None else OpenAICompatibleClient()
    payload = client.complete_json(notice_messages(source_text))
    return validate_notice_result(payload, source_text, source_url)


def generate_newsletter(items, *, client=None):
    """从调用方已筛选的有效资讯生成草稿；来源链接由后端回填。"""
    validate_newsletter_input(items)
    client = client if client is not None else OpenAICompatibleClient()
    payload = client.complete_json(newsletter_messages(items))
    return validate_newsletter_result(payload, items)
