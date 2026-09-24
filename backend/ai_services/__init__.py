"""AI 内部服务入口；导入此包不会调用模型或操作数据库。"""

from .services import extract_notice, generate_newsletter

__all__ = ['extract_notice', 'generate_newsletter']
