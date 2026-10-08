"""兼容旧导入路径；业务错误定义位于 common.errors。"""
from common.errors import BusinessError, check

__all__ = ["BusinessError", "check"]
